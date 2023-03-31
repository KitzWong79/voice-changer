import sys
import os
if sys.platform.startswith('darwin'):
    baseDir = [x for x in sys.path if x.endswith("Contents/MacOS")]
    if len(baseDir) != 1:
        print("baseDir should be only one ", baseDir)
        sys.exit()
    modulePath = os.path.join(baseDir[0], "DDSP-SVC")
    sys.path.append(modulePath)
else:
    sys.path.append("DDSP-SVC")

import io
from dataclasses import dataclass, asdict, field
from functools import reduce
import numpy as np
import torch
import onnxruntime
import pyworld as pw
import ddsp.vocoder as vo
from ddsp.core import upsample
from enhancer import Enhancer
from slicer import Slicer
import librosa
providers = ['OpenVINOExecutionProvider', "CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"]

import resampy
from scipy.io import wavfile
SAMPLING_RATE = 44100


@dataclass
class DDSP_SVCSettings():
    gpu: int = 0
    dstId: int = 0

    f0Detector: str = "dio"  # dio or harvest
    tran: int = 20
    noiceScale: float = 0.3
    predictF0: int = 0  # 0:False, 1:True
    silentThreshold: float = 0.00001
    extraConvertSize: int = 1024 * 32
    clusterInferRatio: float = 0.1

    framework: str = "PyTorch"  # PyTorch or ONNX
    pyTorchModelFile: str = ""
    onnxModelFile: str = ""
    configFile: str = ""

    speakers: dict[str, int] = field(
        default_factory=lambda: {}
    )

    # ↓mutableな物だけ列挙
    intData = ["gpu", "dstId", "tran", "predictF0", "extraConvertSize"]
    floatData = ["noiceScale", "silentThreshold", "clusterInferRatio"]
    strData = ["framework", "f0Detector"]


class DDSP_SVC:
    def __init__(self, params):
        self.settings = DDSP_SVCSettings()
        self.net_g = None
        self.onnx_session = None

        self.raw_path = io.BytesIO()
        self.gpu_num = torch.cuda.device_count()
        self.prevVol = 0
        self.params = params
        print("DDSP-SVC initialization:", params)

    def loadModel(self, config: str, pyTorch_model_file: str = None, onnx_model_file: str = None, clusterTorchModel: str = None):

        self.settings.configFile = config
        # model
        model, args = vo.load_model(pyTorch_model_file)
        self.model = model
        self.args = args
        self.hop_size = int(self.args.data.block_size * SAMPLING_RATE / self.args.data.sampling_rate)

        # hubert
        vec_path = self.params["hubert"]
        self.encoder = vo.Units_Encoder(
            args.data.encoder,
            vec_path,
            args.data.encoder_sample_rate,
            args.data.encoder_hop_size,
            device="cpu")

        # ort_options = onnxruntime.SessionOptions()
        # ort_options.intra_op_num_threads = 8
        # self.onnx_session = onnxruntime.InferenceSession(
        #     "model_DDSP-SVC/hubert4.0.onnx",
        #     providers=providers
        # )
        # inputs = self.onnx_session.get_inputs()
        # outputs = self.onnx_session.get_outputs()
        # for input in inputs:
        #     print("input::::", input)
        # for output in outputs:
        #     print("output::::", output)

        # f0dec
        self.f0_detector = vo.F0_Extractor(
            # "crepe",
            self.settings.f0Detector,
            SAMPLING_RATE,
            self.hop_size,
            float(50),
            float(1100))

        self.volume_extractor = vo.Volume_Extractor(self.hop_size)
        self.enhancer = Enhancer(self.args.enhancer.type, "./model_DDSP-SVC/enhancer/model", "cpu")
        return self.get_info()

    def update_setteings(self, key: str, val: any):
        if key == "onnxExecutionProvider" and self.onnx_session != None:
            if val == "CUDAExecutionProvider":
                if self.settings.gpu < 0 or self.settings.gpu >= self.gpu_num:
                    self.settings.gpu = 0
                provider_options = [{'device_id': self.settings.gpu}]
                self.onnx_session.set_providers(providers=[val], provider_options=provider_options)
            else:
                self.onnx_session.set_providers(providers=[val])
        elif key in self.settings.intData:
            setattr(self.settings, key, int(val))
            if key == "gpu" and val >= 0 and val < self.gpu_num and self.onnx_session != None:
                providers = self.onnx_session.get_providers()
                print("Providers:", providers)
                if "CUDAExecutionProvider" in providers:
                    provider_options = [{'device_id': self.settings.gpu}]
                    self.onnx_session.set_providers(providers=["CUDAExecutionProvider"], provider_options=provider_options)
        elif key in self.settings.floatData:
            setattr(self.settings, key, float(val))
        elif key in self.settings.strData:
            setattr(self.settings, key, str(val))
        else:
            return False

        return True

    def get_info(self):
        data = asdict(self.settings)

        data["onnxExecutionProviders"] = self.onnx_session.get_providers() if self.onnx_session != None else []
        files = ["configFile", "pyTorchModelFile", "onnxModelFile"]
        for f in files:
            if data[f] != None and os.path.exists(data[f]):
                data[f] = os.path.basename(data[f])
            else:
                data[f] = ""

        return data

    def get_processing_sampling_rate(self):
        return SAMPLING_RATE

    def generate_input(self, newData: any, inputSize: int, crossfadeSize: int):
        newData = newData.astype(np.float32) / 32768.0

        if hasattr(self, "audio_buffer"):
            self.audio_buffer = np.concatenate([self.audio_buffer, newData], 0)  # 過去のデータに連結
        else:
            self.audio_buffer = newData

        convertSize = inputSize + crossfadeSize + self.settings.extraConvertSize
        if convertSize % self.hop_size != 0:  # モデルの出力のホップサイズで切り捨てが発生するので補う。
            convertSize = convertSize + (self.hop_size - (convertSize % self.hop_size))

        self.audio_buffer = self.audio_buffer[-1 * convertSize:]  # 変換対象の部分だけ抽出

        # f0
        f0 = self.f0_detector.extract(self.audio_buffer * 32768.0, uv_interp=True)
        f0 = torch.from_numpy(f0).float().unsqueeze(-1).unsqueeze(0)
        f0 = f0 * 2 ** (float(self.settings.tran) / 12)

        # volume, mask
        volume = self.volume_extractor.extract(self.audio_buffer)
        mask = (volume > 10 ** (float(-60) / 20)).astype('float')
        mask = np.pad(mask, (4, 4), constant_values=(mask[0], mask[-1]))
        mask = np.array([np.max(mask[n: n + 9]) for n in range(len(mask) - 8)])
        mask = torch.from_numpy(mask).float().unsqueeze(-1).unsqueeze(0)
        mask = upsample(mask, self.args.data.block_size).squeeze(-1)
        volume = torch.from_numpy(volume).float().unsqueeze(-1).unsqueeze(0)

        # embed
        audio = torch.from_numpy(self.audio_buffer).float().unsqueeze(0)
        seg_units = self.encoder.encode(audio, SAMPLING_RATE, self.hop_size)

        crop = self.audio_buffer[-1 * (inputSize + crossfadeSize):-1 * (crossfadeSize)]

        rms = np.sqrt(np.square(crop).mean(axis=0))
        vol = max(rms, self.prevVol * 0.0)
        self.prevVol = vol

        return (seg_units, f0, volume, mask, convertSize, vol)

    def _onnx_inference(self, data):
        if hasattr(self, "onnx_session") == False or self.onnx_session == None:
            print("[Voice Changer] No onnx session.")
            return np.zeros(1).astype(np.int16)

        seg_units = data[0]
        # f0 = data[1]
        # convertSize = data[2]
        # vol = data[3]

        if vol < self.settings.silentThreshold:
            return np.zeros(convertSize).astype(np.int16)

        c, f0, uv = [x.numpy() for x in data]
        audio1 = self.onnx_session.run(
            ["audio"],
            {
                "c": c,
                "f0": f0,
                "g": np.array([self.settings.dstId]).astype(np.int64),
                "uv": np.array([self.settings.dstId]).astype(np.int64),
                "predict_f0": np.array([self.settings.dstId]).astype(np.int64),
                "noice_scale": np.array([self.settings.dstId]).astype(np.int64),


            })[0][0, 0] * self.hps.data.max_wav_value

        audio1 = audio1 * vol

        result = audio1

        return result

        pass

    def _pyTorch_inference(self, data):

        if hasattr(self, "model") == False or self.model == None:
            print("[Voice Changer] No pyTorch session.")
            return np.zeros(1).astype(np.int16)

        c = data[0]
        f0 = data[1]
        volume = data[2]
        mask = data[3]

        convertSize = data[4]
        vol = data[5]

        # if vol < self.settings.silentThreshold:
        #     print("threshold")
        #     return np.zeros(convertSize).astype(np.int16)

        with torch.no_grad():
            spk_id = torch.LongTensor(np.array([[int(1)]]))
            seg_output, _, (s_h, s_n) = self.model(c, f0, volume, spk_id=spk_id, spk_mix_dict=None)
            seg_output *= mask

            seg_output, output_sample_rate = self.enhancer.enhance(
                seg_output,
                self.args.data.sampling_rate,
                f0,
                self.args.data.block_size,
                adaptive_key=float(3))
            result = seg_output.squeeze().cpu().numpy() * 32768.0
        return np.array(result).astype(np.int16)

    def inference(self, data):
        if self.settings.framework == "ONNX":
            audio = self._onnx_inference(data)
        else:
            audio = self._pyTorch_inference(data)
        return audio

    def destroy(self):
        del self.net_g
        del self.onnx_session


def cross_fade(a: np.ndarray, b: np.ndarray, idx: int):
    result = np.zeros(idx + b.shape[0])
    fade_len = a.shape[0] - idx
    np.copyto(dst=result[:idx], src=a[:idx])
    k = np.linspace(0, 1.0, num=fade_len, endpoint=True)
    result[idx: a.shape[0]] = (1 - k) * a[idx:] + k * b[: fade_len]
    np.copyto(dst=result[a.shape[0]:], src=b[fade_len:])
    return result

import { ServerInfo, ServerSettingKey } from "./const";


type FileChunk = {
    hash: number,
    chunk: ArrayBuffer
}
export class ServerConfigurator {
    private serverUrl = ""

    setServerUrl = (serverUrl: string) => {
        this.serverUrl = serverUrl
        console.log(`[ServerConfigurator] Server URL: ${this.serverUrl}`)
    }

    getSettings = async () => {
        const url = this.serverUrl + "/info"
        const info = await new Promise<ServerInfo>((resolve) => {
            const request = new Request(url, {
                method: 'GET',
            });
            fetch(request).then(async (response) => {
                const json = await response.json() as ServerInfo
                resolve(json)
            })
        })
        return info
    }

    updateSettings = async (key: ServerSettingKey, val: string) => {
        const url = this.serverUrl + "/update_setteings"
        const info = await new Promise<ServerInfo>(async (resolve) => {
            const formData = new FormData();
            formData.append("key", key);
            formData.append("val", val);
            const request = new Request(url, {
                method: 'POST',
                body: formData,
            });
            const res = await (await fetch(request)).json() as ServerInfo
            resolve(res)
        })
        return info
    }

    uploadFile = async (buf: ArrayBuffer, filename: string, onprogress: (progress: number, end: boolean) => void) => {
        const url = this.serverUrl + "/upload_file"
        onprogress(0, false)
        const size = 1024 * 1024;
        const fileChunks: FileChunk[] = [];
        let index = 0; // index値
        for (let cur = 0; cur < buf.byteLength; cur += size) {
            fileChunks.push({
                hash: index++,
                chunk: buf.slice(cur, cur + size),
            });
        }

        const chunkNum = fileChunks.length
        // console.log("FILE_CHUNKS:", chunkNum, fileChunks)


        while (true) {
            const promises: Promise<void>[] = []
            for (let i = 0; i < 10; i++) {
                const chunk = fileChunks.shift()
                if (!chunk) {
                    break
                }
                const p = new Promise<void>((resolve) => {
                    const formData = new FormData();
                    formData.append("file", new Blob([chunk.chunk]));
                    formData.append("filename", `${filename}_${chunk.hash}`);
                    const request = new Request(url, {
                        method: 'POST',
                        body: formData,
                    });
                    fetch(request).then(async (_response) => {
                        // console.log(await response.text())
                        resolve()
                    })
                })

                promises.push(p)
            }
            await Promise.all(promises)
            if (fileChunks.length == 0) {
                break
            }
            onprogress(Math.floor(((chunkNum - fileChunks.length) / (chunkNum + 1)) * 100), false)
        }
        return chunkNum
    }

    concatUploadedFile = async (filename: string, chunkNum: number) => {
        const url = this.serverUrl + "/concat_uploaded_file"
        await new Promise<void>((resolve) => {
            const formData = new FormData();
            formData.append("filename", filename);
            formData.append("filenameChunkNum", "" + chunkNum);
            const request = new Request(url, {
                method: 'POST',
                body: formData,
            });
            fetch(request).then(async (response) => {
                console.log(await response.text())
                resolve()
            })
        })
    }

    // !! 注意!! hubertTorchModelは固定値で上書きされるため、設定しても効果ない。
    loadModel = async (configFilename: string, pyTorchModelFilename: string | null, onnxModelFilename: string | null, clusterTorchModelFilename: string | null, hubertTorchModelFilename: string | null) => {
        const url = this.serverUrl + "/load_model"
        const info = new Promise<ServerInfo>(async (resolve) => {
            const formData = new FormData();
            formData.append("pyTorchModelFilename", pyTorchModelFilename || "-");
            formData.append("onnxModelFilename", onnxModelFilename || "-");
            formData.append("configFilename", configFilename);
            formData.append("clusterTorchModelFilename", clusterTorchModelFilename || "-");
            formData.append("hubertTorchModelFilename", hubertTorchModelFilename || "-");

            const request = new Request(url, {
                method: 'POST',
                body: formData,
            });
            const res = await (await fetch(request)).json() as ServerInfo
            resolve(res)
        })
        return await info
    }

}
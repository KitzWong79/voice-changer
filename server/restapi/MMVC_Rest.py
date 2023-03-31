from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Callable
from voice_changer.VoiceChangerManager import VoiceChangerManager

from restapi.MMVC_Rest_Hello import MMVC_Rest_Hello
from restapi.MMVC_Rest_VoiceChanger import MMVC_Rest_VoiceChanger
from restapi.MMVC_Rest_Fileuploader import MMVC_Rest_Fileuploader
from restapi.MMVC_Rest_Trainer import MMVC_Rest_Trainer
from const import getFrontendPath, TMP_DIR


class ValidationErrorLoggingRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except Exception as exc:
                print("Exception", request.url, str(exc))
                body = await request.body()
                detail = {"errors": exc.errors(), "body": body.decode()}
                raise HTTPException(status_code=422, detail=detail)

        return custom_route_handler


class MMVC_Rest:

    @classmethod
    def get_instance(cls, voiceChangerManager: VoiceChangerManager):
        if not hasattr(cls, "_instance"):
            app_fastapi = FastAPI()
            app_fastapi.router.route_class = ValidationErrorLoggingRoute
            app_fastapi.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

            app_fastapi.mount(
                "/front", StaticFiles(directory=f'{getFrontendPath()}', html=True), name="static")

            app_fastapi.mount(
                "/trainer", StaticFiles(directory=f'{getFrontendPath()}', html=True), name="static")

            app_fastapi.mount(
                "/recorder", StaticFiles(directory=f'{getFrontendPath()}', html=True), name="static")
            app_fastapi.mount(
                "/tmp", StaticFiles(directory=f'{TMP_DIR}'), name="static")

            restHello = MMVC_Rest_Hello()
            app_fastapi.include_router(restHello.router)
            restVoiceChanger = MMVC_Rest_VoiceChanger(voiceChangerManager)
            app_fastapi.include_router(restVoiceChanger.router)
            fileUploader = MMVC_Rest_Fileuploader(voiceChangerManager)
            app_fastapi.include_router(fileUploader.router)
            trainer = MMVC_Rest_Trainer()
            app_fastapi.include_router(trainer.router)

            cls._instance = app_fastapi
            return cls._instance

        return cls._instance

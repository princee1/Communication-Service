"""
Contains the FastAPI app
"""

from starlette.types import ASGIApp
from services.config_service import ConfigService
from services.security_service import SecurityService
from definition._ressource import Ressource
from container import InjectInMethod, Get, Need
from fastapi import Request, Response, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from typing import Any, Awaitable, Callable, MutableMapping
import time
from interface.middleware import EventInterface, InjectableMiddlewareInterface
import uvicorn
import multiprocessing
import threading
import signal,sys


def handle_sigint(signal_num, frame):
    print(frame)
    print("Custom SIGINT handler: Cleanup before shutdown...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)





class ProcessTimeMiddleWare(BaseHTTPMiddleware):

    def __init__(self, app, dispatch=None) -> None:
        super().__init__(self, app, dispatch)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


class SecurityMiddleWare(BaseHTTPMiddleware, InjectableMiddlewareInterface):

    def __init__(self, app, dispatch=None) -> None:
        BaseHTTPMiddleware.__init__(self, app, dispatch)
        InjectableMiddlewareInterface.__init__(self)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        response: Response = await call_next(request)
        return response

    @InjectInMethod
    def inject_middleware(self, securityService: SecurityService):
        self.securityService = securityService


class Application(threading.Thread, EventInterface):

    def __init__(self, title: str, summary: str, description: str, ressources: list[type[Ressource]], middlewares: list[type[BaseHTTPMiddleware]]) -> None:
        threading.Thread.__init__(self, None, None, title, daemon=None)
        self.ressources = ressources
        self.middlewares = middlewares
        self.configService: ConfigService = Get(ConfigService, None, False)
        self.app = FastAPI(title=title, summary=summary, description=description,
                           on_shutdown=[self.on_shutdown], on_startup=[self.on_startup])
        self.add_middlewares()
        self.add_ressources()
        pass

    def start_server(self):
        uvicorn.run(self.app,)

    def stop_server(self):
        pass

    def run(self) -> None:
        self.start_server()

    def add_ressources(self):
        for ressource_type in self.ressources:
            res = ressource_type()
            self.app.include_router(res.router)
        pass

    def add_middlewares(self):
        for middleware in self.middlewares:
            self.app.add_middleware(middleware)

    def on_startup(self):
        pass

    def on_shutdown(self):
        pass

    pass

import uuid

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import api_router
from config import settings
from errors import AppError, error_body

app = FastAPI(title="语音约碰面地点", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))


def _stage_from_path(path: str) -> str:
    if path.rstrip("/").endswith("/upload"):
        return "upload"
    return "unknown"


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(_request_id(request), exc.code, exc.message, exc.stage),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request,
    _exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_body(
            _request_id(request),
            "VALIDATION_ERROR",
            "请求缺少文件或字段类型不正确。",
            _stage_from_path(request.url.path),
        ),
    )


app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
    )

# app/core/exceptions.py
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger


class AppException(HTTPException):
    def __init__(
            self,
            status_code: int,
            detail: str,
            error_code: str = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code


async def app_exception_handler(request: Request, exc: AppException):
    # Using structured logging that matches your LoggerManager format
    logger.bind(
        error_code=exc.error_code,
        request_path=str(request.url.path),
        request_method=request.method
    ).error(f"AppException: {exc.detail}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.detail
            }
        }
    )


class NotFoundError(AppException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=404,
            detail=detail,
            error_code="NOT_FOUND"
        )


class ValidationError(AppException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=400,
            detail=detail,
            error_code="VALIDATION_ERROR"
        )
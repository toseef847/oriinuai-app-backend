from typing import Any, Generic, Mapping, TypeVar
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    status: int
    message: str
    data: T | None = None


def api_success(
    data: Any = None, message: str = "Operation successful", status_code: int = 200
) -> JSONResponse:
    """
    Returns a standardized successful JSON response.
    """
    content = jsonable_encoder(
        {"status": status_code, "message": message, "data": data}
    )
    return JSONResponse(status_code=status_code, content=content)


def api_error(
    message: str = "An error occurred",
    status_code: int = 400,
    data: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """
    Returns a standardized error JSON response.
    """
    content = jsonable_encoder(
        {"status": status_code, "message": message, "data": data}
    )
    return JSONResponse(status_code=status_code, content=content, headers=headers)

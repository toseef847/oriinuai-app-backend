from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GoogleErrorDetails:
    status_code: int
    message: str


class FriendlyGoogleError(Exception):
    """A sanitized Google service error that is safe to expose to clients."""

    def __init__(self, details: GoogleErrorDetails):
        super().__init__(details.message)
        self.status_code = details.status_code
        self.user_message = details.message


_ERROR_MESSAGES = {
    400: "We couldn't process that request. Please revise it and try again.",
    403: "The AI service is not available right now. Please try again later.",
    404: "The AI service could not complete that request. Please try again later.",
    429: "ORIINU is receiving many requests right now. Please wait a moment and try again.",
    499: "The request was cancelled before it could be completed.",
    500: "The AI service encountered a temporary problem. Please try again.",
    503: "The AI service is temporarily unavailable. Please try again shortly.",
    504: "The request took too long to complete. Please shorten it and try again.",
}

_STATUS_TO_CODE = {
    "INVALID_ARGUMENT": 400,
    "FAILED_PRECONDITION": 403,
    "PERMISSION_DENIED": 403,
    "NOT_FOUND": 404,
    "RESOURCE_EXHAUSTED": 429,
    "CANCELLED": 499,
    "INTERNAL": 500,
    "UNAVAILABLE": 503,
    "DEADLINE_EXCEEDED": 504,
}


def _response_status(exception: Exception) -> str:
    status = getattr(exception, "status", None)
    if status:
        return str(status).upper()
    response_json: Any = getattr(exception, "response_json", None)
    if isinstance(response_json, dict):
        error = response_json.get("error", response_json)
        if isinstance(error, dict):
            return str(error.get("status", "")).upper()
    return ""


def translate_google_error(exception: Exception) -> GoogleErrorDetails:
    """Translate a Google SDK exception without exposing provider details."""
    raw_code = getattr(exception, "code", None)
    try:
        code = int(raw_code)
    except (TypeError, ValueError):
        code = None

    searchable = f"{_response_status(exception)} {exception}".upper()
    status_code = next(
        (mapped for status, mapped in _STATUS_TO_CODE.items() if status in searchable),
        None,
    )
    if status_code is not None:
        code = status_code
    elif code not in _ERROR_MESSAGES:
        code = 500

    return GoogleErrorDetails(
        status_code=code,
        message=_ERROR_MESSAGES.get(code, _ERROR_MESSAGES[500]),
    )

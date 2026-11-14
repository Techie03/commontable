"""Error envelope: every error response is {"error": {"code", "message"}}."""

from fastapi import HTTPException


class ApiError(HTTPException):
    """HTTPException carrying a machine-readable error code."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code=status_code, detail=message)
        self.code = code


def not_found(message: str = "Not found") -> ApiError:
    return ApiError(404, "not_found", message)


def forbidden(message: str = "You do not have permission to do that") -> ApiError:
    return ApiError(403, "forbidden", message)


def unauthorized(message: str = "Authentication required") -> ApiError:
    return ApiError(401, "unauthorized", message)


def bad_request(message: str, code: str = "bad_request") -> ApiError:
    return ApiError(400, code, message)


def conflict(message: str, code: str = "conflict") -> ApiError:
    return ApiError(409, code, message)


def unprocessable(message: str) -> ApiError:
    return ApiError(422, "unprocessable", message)


def bad_gateway(message: str) -> ApiError:
    return ApiError(502, "bad_gateway", message)


def service_unavailable(message: str, code: str = "service_unavailable") -> ApiError:
    return ApiError(503, code, message)

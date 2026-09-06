class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, stage: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.stage = stage
        super().__init__(message)


def error_body(request_id: str, code: str, message: str, stage: str) -> dict:
    return {
        "request_id": request_id,
        "error": {
            "code": code,
            "message": message,
            "stage": stage,
        },
    }

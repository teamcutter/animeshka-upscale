class AppError(Exception):
    status_code: int = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404


class PayloadTooLargeError(AppError):
    status_code = 413


class UnsupportedMediaTypeError(AppError):
    status_code = 415


class InvalidMediaError(AppError):
    status_code = 422


class JobNotReadyError(AppError):
    status_code = 409

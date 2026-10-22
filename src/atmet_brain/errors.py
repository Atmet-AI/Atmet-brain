"""Errors that can safely cross an API boundary."""


class BrainError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def as_dict(self):
        return {"code": self.code, "message": self.message}


def require(condition, code, message, status=400):
    if not condition:
        raise BrainError(code, message, status)

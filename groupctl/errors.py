"""Public failure categories shared by the CLI and mechanical helpers."""


class GroupError(Exception):
    def __init__(self, message, *, code=1, hint=None):
        super().__init__(message)
        self.code = code
        self.hint = hint


class VerificationError(GroupError):
    def __init__(self, message, *, hint=None):
        super().__init__(message, code=2, hint=hint)

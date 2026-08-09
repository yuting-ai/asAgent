class ToolArgumentsValidationError(RuntimeError):
    pass


class ToolApprovalDeniedError(RuntimeError):
    pass


class ToolPermissionDeniedError(RuntimeError):
    pass


class ToolTimeoutError(RuntimeError):
    pass

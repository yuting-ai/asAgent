class ToolArgumentsValidationError(RuntimeError):
    pass


class ToolApprovalDeniedError(RuntimeError):
    pass


class ToolPermissionDeniedError(RuntimeError):
    pass


class ToolTimeoutError(RuntimeError):
    pass


SAFE_BROWSER_OPERATION_ERRORS = frozenset(
    {
        "target was not found",
        "target is not visible",
        "target is obscured",
        "target is not editable",
        "target is not selectable",
        "option was not found",
        "option is disabled",
        "page changed; inspect interactive elements again",
        "current browser tab is not visible",
    }
)


class ToolOperationError(RuntimeError):
    """Controlled, model-safe tool failure with an allowlisted message."""

    def __init__(self, message: str) -> None:
        if message not in SAFE_BROWSER_OPERATION_ERRORS:
            raise ValueError("tool operation error message is not allowlisted")
        super().__init__(message)

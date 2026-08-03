from enum import StrEnum


class RunStatus(StrEnum):
    CREATED = "created"
    PREPARING = "preparing"
    CALLING_MODEL = "calling_model"
    MODEL_RESPONDED = "model_responded"
    EXECUTING_TOOLS = "executing_tools"
    APPENDING_RESULTS = "appending_results"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    LIMIT_REACHED = "limit_reached"

    @property
    def is_terminal(self) -> bool:
        return self in {
            RunStatus.COMPLETED,
            RunStatus.CANCELLED,
            RunStatus.FAILED,
            RunStatus.LIMIT_REACHED,
        }

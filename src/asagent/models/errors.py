from typing import ClassVar


class ProviderError(RuntimeError):
    retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProviderConfigurationError(ProviderError):
    pass


class ProviderAuthenticationError(ProviderError):
    pass


class ProviderBillingError(ProviderError):
    pass


class ProviderRequestError(ProviderError):
    pass


class ProviderResponseError(ProviderError):
    pass


class ProviderTransportError(ProviderError):
    pass


class ProviderTimeoutError(ProviderTransportError):
    pass


class ProviderRateLimitError(ProviderError):
    retryable = True


class ProviderServiceError(ProviderError):
    retryable = True

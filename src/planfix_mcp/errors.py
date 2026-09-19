class PlanfixMcpError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigError(PlanfixMcpError):
    pass


class AuthError(PlanfixMcpError):
    pass


class RouteError(PlanfixMcpError):
    pass


class PlanfixRequestError(PlanfixMcpError):
    pass

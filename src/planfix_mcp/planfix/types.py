from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SessionCookies:
    phpsessid: str
    rtoken: str


class Authenticator(Protocol):
    async def authenticate(self) -> SessionCookies: ...

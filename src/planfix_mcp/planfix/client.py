import asyncio
import logging
from typing import Any

import aiohttp
import orjson

from planfix_mcp.errors import AuthError, PlanfixRequestError, RouteError
from planfix_mcp.planfix.origin import absolute_https_url, https_origin, normalize_domain
from planfix_mcp.planfix.rate_limit import RateLimiter
from planfix_mcp.planfix.types import Authenticator, SessionCookies
from planfix_mcp.routing.safety import assert_j_path, assert_referer

logger = logging.getLogger(__name__)

_AUTH_STATUSES = frozenset({401, 403})
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024


def _session_is_alive(body: Any) -> bool:
    if not isinstance(body, dict):
        return False
    result = str(body.get('Result') or body.get('result') or '').lower()
    if result == 'success':
        return True
    if result == 'error':
        return False
    return 'currentServerTime' in body


def _is_unauthorised(status: int, body: Any) -> bool:
    if status == 401:
        return True
    if not isinstance(body, dict):
        return False
    result = str(body.get('Result') or body.get('result') or '').lower()
    if status not in _AUTH_STATUSES and result != 'error':
        return False
    error = str(body.get('Error') or body.get('error') or '').lower()
    return 'not authorised' in error or 'not authorized' in error


def _planfix_error_message(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    result = str(body.get('Result') or body.get('result') or '').lower()
    if result != 'error':
        return None
    raw = body.get('Error') or body.get('error')
    if not isinstance(raw, str):
        return 'Planfix returned an error'
    detail = ' '.join(raw.split())
    if not detail:
        return 'Planfix returned an error'
    return f'Planfix error: {detail[:200]}'


class PlanfixClient:
    __slots__ = (
        '_auth',
        '_auth_generation',
        '_cookies',
        '_domain',
        '_exchange_lock',
        '_language',
        '_limiter',
        '_login_lock',
        '_owns_session',
        '_session',
        '_transaction_lock',
        '_url',
    )

    def __init__(
        self,
        *,
        domain: str,
        language: str = 'Ru',
        authenticator: Authenticator,
        limiter: RateLimiter,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        try:
            self._domain = normalize_domain(domain)
        except ValueError as exc:
            raise AuthError('PF_DOMAIN must be a valid hostname') from exc
        self._auth = authenticator
        self._language = language
        self._limiter = limiter
        self._session = session
        self._owns_session = session is None
        self._login_lock = asyncio.Lock()
        self._exchange_lock = asyncio.Lock()
        self._transaction_lock = asyncio.Lock()
        self._auth_generation = 0
        self._cookies: SessionCookies | None = None
        self._url = f'https://{self._domain}/ajax/'

    @property
    def connected(self) -> bool:
        return self._cookies is not None

    @property
    def cookies(self) -> SessionCookies | None:
        return self._cookies

    async def _http(self) -> aiohttp.ClientSession:
        session = self._session
        if session is None:
            self._session = aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar())
            self._owns_session = True
            return self._session
        if self._owns_session and session.closed:
            self._session = aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar())
            return self._session
        return session

    async def login(self) -> None:
        generation = self._auth_generation
        async with self._login_lock:
            if self._cookies is not None:
                return
            if generation != self._auth_generation:
                return
            logger.info('Planfix login via browser')
            cookies = await self._auth.authenticate()
            if not cookies.phpsessid or not cookies.rtoken:
                raise AuthError('Planfix login returned empty session cookies')
            if generation != self._auth_generation:
                return
            self._cookies = cookies

    async def ping(self) -> bool:
        async with self._transaction_lock:
            return await self._ping_locked()

    async def _ping_locked(self) -> bool:
        if self._cookies is None:
            return False
        try:
            body, status = await self._exchange(
                {'command': 'login:getCurrentTime'},
                retry_on_token=True,
                url=self._url,
            )
        except AuthError, PlanfixRequestError:
            self.clear_cookies()
            return False
        if status != 200 or not _session_is_alive(body):
            self.clear_cookies()
            return False
        return True

    async def execute(self, payload: dict[str, str], *, authenticate: bool = True) -> Any:
        async with self._transaction_lock:
            return await self._execute_locked(payload, authenticate=authenticate, url=self._url)

    async def execute_path(
        self,
        path: str,
        payload: dict[str, str],
        *,
        referer: str,
        authenticate: bool = True,
    ) -> Any:
        try:
            url = absolute_https_url(self._domain, assert_j_path(path))
            referer_url = absolute_https_url(self._domain, assert_referer(referer))
        except (RouteError, ValueError) as exc:
            message = exc.message if isinstance(exc, RouteError) else 'Invalid Planfix path'
            raise RouteError(message) from exc
        extra_headers = {
            'Origin': https_origin(self._domain),
            'Referer': referer_url,
        }
        async with self._transaction_lock:
            return await self._execute_locked(
                payload,
                authenticate=authenticate,
                url=url,
                extra_headers=extra_headers,
            )

    async def _execute_locked(
        self,
        payload: dict[str, str],
        *,
        authenticate: bool,
        url: str,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        if authenticate:
            await self.login()
        body, status = await self._exchange(
            payload,
            retry_on_token=True,
            url=url,
            extra_headers=extra_headers,
        )
        if authenticate and _is_unauthorised(status, body):
            self.clear_cookies()
            await self.login()
            body, status = await self._exchange(
                payload,
                retry_on_token=True,
                url=url,
                extra_headers=extra_headers,
            )
            if _is_unauthorised(status, body):
                self.clear_cookies()
        if status != 200:
            raise PlanfixRequestError(f'Planfix returned {status}')
        if body is None:
            raise PlanfixRequestError('Planfix returned empty response')
        error = _planfix_error_message(body)
        if error is not None:
            raise PlanfixRequestError(error)
        return body

    async def _exchange(
        self,
        payload: dict[str, str],
        *,
        retry_on_token: bool,
        url: str,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[Any, int]:
        async with self._exchange_lock:
            return await self._exchange_locked(
                payload,
                retry_on_token=retry_on_token,
                url=url,
                extra_headers=extra_headers,
            )

    async def _exchange_locked(
        self,
        payload: dict[str, str],
        *,
        retry_on_token: bool,
        url: str,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[Any, int]:
        cookies = self._cookies
        if cookies is None:
            raise AuthError('Planfix session is not authenticated')
        headers = {
            'Host': self._domain,
            'X-RToken': cookies.rtoken,
            'X-Requested-With': 'XMLHttpRequest',
        }
        if extra_headers:
            headers.update(extra_headers)
        http = await self._http()
        await self._limiter.acquire()
        try:
            async with http.post(
                url,
                headers=headers,
                cookies={
                    'Lang': self._language,
                    'PHPSESSID': cookies.phpsessid,
                    'RememberMeSet': '0',
                    'rtoken': cookies.rtoken,
                },
                data=payload,
                allow_redirects=False,
            ) as response:
                changed = self._apply_response_cookies(response, cookies)
                body = await self._parse_body(response)
                if retry_on_token and changed and response.status in _AUTH_STATUSES:
                    return await self._exchange_locked(
                        payload,
                        retry_on_token=False,
                        url=url,
                        extra_headers=extra_headers,
                    )
                return body, response.status
        except (TimeoutError, aiohttp.ClientError) as exc:
            raise PlanfixRequestError('Planfix request failed') from exc

    def _apply_response_cookies(
        self,
        response: aiohttp.ClientResponse,
        expected: SessionCookies,
    ) -> bool:
        current = self._cookies
        if current != expected:
            return False
        phpsessid = current.phpsessid
        rtoken = current.rtoken
        for name, morsel in response.cookies.items():
            value = morsel.value
            if not value:
                continue
            if name == 'PHPSESSID':
                phpsessid = value
            elif name == 'rtoken':
                rtoken = value
        if phpsessid == current.phpsessid and rtoken == current.rtoken:
            return False
        self._cookies = SessionCookies(phpsessid=phpsessid, rtoken=rtoken)
        return True

    async def _parse_body(self, response: aiohttp.ClientResponse) -> Any:
        content = bytearray()
        async for chunk in response.content.iter_chunked(64 * 1024):
            if len(content) + len(chunk) > _MAX_RESPONSE_BYTES:
                raise PlanfixRequestError('Planfix response is too large')
            content.extend(chunk)
        if not content.strip():
            return None
        try:
            return orjson.loads(content)
        except ValueError as exc:
            if response.status != 200:
                return None
            raise PlanfixRequestError(f'Planfix returned non-JSON ({response.status})') from exc

    def clear_cookies(self) -> None:
        self._auth_generation += 1
        self._cookies = None

    async def close(self) -> None:
        session = self._session
        if not self._owns_session or session is None:
            return
        self._session = None
        await session.close()

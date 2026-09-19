import math
from typing import Any, Protocol

from planfix_mcp.config import SETTINGS
from planfix_mcp.errors import ConfigError, RouteError
from planfix_mcp.limit import Profile
from planfix_mcp.planfix.auth import PlaywrightAuthenticator
from planfix_mcp.planfix.client import PlanfixClient
from planfix_mcp.planfix.origin import normalize_domain
from planfix_mcp.planfix.rate_limit import RateLimiter
from planfix_mcp.routing.aliases import normalize_aspect
from planfix_mcp.routing.manifest import Manifest, classify_command, load_manifest
from planfix_mcp.routing.params import (
    ajax_page_window,
    build_detail_params,
    build_params,
    build_path_params,
    build_raw_params,
    page_window,
)
from planfix_mcp.shape import present_payload

SESSION_ASPECTS = ('status', 'logout')


class SessionClient(Protocol):
    connected: bool

    async def login(self) -> None: ...

    async def ping(self) -> bool: ...

    async def execute(self, payload: dict[str, str]) -> Any: ...

    async def execute_path(self, path: str, payload: dict[str, str], *, referer: str) -> Any: ...

    def clear_cookies(self) -> None: ...

    async def close(self) -> None: ...


class PlanfixRuntime:
    __slots__ = ('_client', '_manifest')

    def __init__(
        self,
        manifest: Manifest | None = None,
        client: SessionClient | None = None,
    ) -> None:
        self._manifest = manifest or load_manifest()
        self._client = client

    @property
    def manifest(self) -> Manifest:
        return self._manifest

    @staticmethod
    def _config_values() -> tuple[str, str, str, str]:
        raw_domain = SETTINGS.pf_domain.strip()
        username = SETTINGS.pf_username.strip()
        password = SETTINGS.pf_password.get_secret_value()
        language = SETTINGS.pf_lang.strip()
        if not raw_domain or not username or not password:
            raise ConfigError('Set PF_DOMAIN, PF_USERNAME, PF_PASSWORD in .env')
        if not language:
            raise ConfigError('PF_LANG must not be empty')
        try:
            domain = normalize_domain(raw_domain)
        except ValueError as exc:
            raise ConfigError('PF_DOMAIN must be a valid hostname without scheme, port, or path') from exc
        if not math.isfinite(SETTINGS.browser_timeout) or SETTINGS.browser_timeout <= 0:
            raise ConfigError('PF_BROWSER_TIMEOUT must be positive')
        if not math.isfinite(SETTINGS.rps) or SETTINGS.rps <= 0:
            raise ConfigError('PF_RPS must be positive')
        return domain, username, password, language

    def _build_client(self) -> PlanfixClient:
        domain, username, password, language = self._config_values()
        return PlanfixClient(
            domain=domain,
            language=language,
            authenticator=PlaywrightAuthenticator(
                domain=domain,
                username=username,
                password=password,
                browser_bin=SETTINGS.browser_bin,
                timeout_s=SETTINGS.browser_timeout,
            ),
            limiter=RateLimiter(min(SETTINGS.rps, 1.0)),
        )

    def _get_client(self) -> SessionClient:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    async def status(self) -> dict[str, Any]:
        if self._client is None:
            self._config_values()
            connected = False
        elif self._client.connected:
            connected = await self._client.ping()
        else:
            connected = False
        return {
            'domain': SETTINGS.pf_domain.strip(),
            'username': SETTINGS.pf_username.strip(),
            'connected': connected,
        }

    async def connect(self) -> dict[str, Any]:
        client = self._get_client()
        await client.login()
        return await self.status()

    async def warmup(self) -> None:
        await self.connect()

    async def disconnect(self) -> dict[str, Any]:
        if self._client is not None:
            self._client.clear_cookies()
        return await self.status()

    async def call_block(
        self,
        block: str,
        *,
        aspect: str,
        args: dict[str, Any],
        response_profile: Profile,
    ) -> Any:
        if block not in self._manifest.aspects:
            raise RouteError(f'unknown block "{block}"')
        resolved = normalize_aspect(block, aspect)
        if block == 'session':
            if resolved == 'status':
                return await self.status()
            if resolved == 'logout':
                return await self.disconnect()
        try:
            route = self._manifest.aspect(block, resolved)
        except KeyError as exc:
            raise RouteError(str(exc)) from exc

        # Expand validation runs before any request so a bad call stays side-effect-free.
        detail_params = build_detail_params(block, route, args) if args.get('expand') else None
        if route.kind == 'overview':
            return await self._overview(response_profile)

        client = self._get_client()
        if route.path is None:
            payload = await client.execute(build_params(block, route, args))
        else:
            params = build_path_params(block, route, args)
            if route.referer is None:
                raise RouteError(f'path route {resolved} requires referer')
            payload = await client.execute_path(route.path, params, referer=route.referer)

        offset, page_size = page_window(block, route, args)

        def present(payload: Any, *, kind: str | None = None) -> Any:
            return present_payload(
                payload,
                block=block,
                aspect=resolved,
                kind=kind or route.kind,
                profile=response_profile,
                offset=offset,
                page_size=page_size,
            )

        primary = present(payload)
        if detail_params is None:
            return primary
        return {
            'primary': primary,
            'expanded': present(await client.execute(detail_params), kind='read'),
        }

    async def call_ajax(
        self,
        command: str,
        *,
        params: dict[str, Any] | None,
        response_profile: Profile,
    ) -> Any:
        payload = build_raw_params(
            command,
            params,
            allowed_commands=self._manifest.ajax_commands,
        )
        client = self._get_client()
        body = await client.execute(payload)
        offset, page_size = ajax_page_window(payload['command'], params)
        return present_payload(
            body,
            block='ajax',
            aspect='raw',
            kind=classify_command(payload['command']),
            profile=response_profile,
            offset=offset,
            page_size=page_size,
        )

    async def _overview(self, profile: Profile) -> dict[str, Any]:
        client = self._get_client()
        sections: dict[str, Any] = {}
        for section in self._manifest.overview_sections:
            if section.section == 'is_admin':
                sections[section.section] = {
                    'is_admin': None,
                    'note': 'Call employees aspect=is_admin with a real user/login id',
                }
                continue
            payload = await client.execute({'command': section.command})
            sections[section.section] = present_payload(
                payload,
                block='account_config',
                aspect=section.section,
                kind='read',
                profile=profile,
            )
        return {'aspect': 'overview', 'sections': sections}

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

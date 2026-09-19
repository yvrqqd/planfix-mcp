import asyncio
from typing import Any

from playwright.async_api import BrowserContext, async_playwright
from playwright.async_api import Error as PlaywrightError

from planfix_mcp.errors import AuthError
from planfix_mcp.planfix.chromium import launch_kwargs
from planfix_mcp.planfix.origin import is_same_https_origin, normalize_domain
from planfix_mcp.planfix.types import SessionCookies


def _cookies_from_list(cookies: list[dict[str, Any]]) -> SessionCookies | None:
    phpsessid = ''
    rtoken = ''
    for cookie in cookies:
        name = cookie.get('name')
        value = cookie.get('value')
        if not isinstance(value, str) or not value:
            continue
        if name == 'PHPSESSID':
            phpsessid = value
        elif name == 'rtoken':
            rtoken = value
    if not phpsessid or not rtoken:
        return None
    return SessionCookies(phpsessid=phpsessid, rtoken=rtoken)


class PlaywrightAuthenticator:
    __slots__ = (
        '_browser_bin',
        '_domain',
        '_password',
        '_timeout_ms',
        '_username',
    )

    def __init__(
        self,
        *,
        domain: str,
        username: str,
        password: str,
        browser_bin: str = '',
        timeout_s: float = 60.0,
    ) -> None:
        self._domain = domain
        self._username = username
        self._password = password
        self._browser_bin = browser_bin
        self._timeout_ms = timeout_s * 1000.0

    async def authenticate(self) -> SessionCookies:
        try:
            domain = normalize_domain(self._domain)
        except ValueError as exc:
            raise AuthError('PF_DOMAIN must be a valid hostname') from exc
        base_url = f'https://{domain}'
        login_url = f'{base_url}/?action=login'
        timeout = self._timeout_ms

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    **await asyncio.to_thread(launch_kwargs, self._browser_bin),
                )
                try:
                    context = await browser.new_context()
                    page = await context.new_page()
                    page.set_default_timeout(timeout)
                    await page.goto(login_url, timeout=timeout, wait_until='domcontentloaded')
                    if not is_same_https_origin(page.url, domain):
                        raise AuthError('Planfix login redirected outside the configured origin')
                    username_field = page.locator('input[name="tbUserName"]')
                    password_field = page.locator('input[name="tbUserPassword"]')
                    form_action = await password_field.evaluate('element => element.form?.action || ""')
                    if not isinstance(form_action, str) or (
                        form_action and not is_same_https_origin(form_action, domain)
                    ):
                        raise AuthError('Planfix login form points outside the configured origin')
                    await username_field.fill(self._username)
                    await password_field.fill(self._password)
                    await password_field.press('Enter')
                    return await self._wait_for_cookies(context, base_url, timeout / 1000.0)
                finally:
                    await browser.close()
        except AuthError:
            raise
        except PlaywrightError as exc:
            raise AuthError('Planfix browser login failed') from exc

    async def _wait_for_cookies(
        self,
        context: BrowserContext,
        base_url: str,
        timeout_s: float,
    ) -> SessionCookies:
        deadline = asyncio.get_running_loop().time() + timeout_s
        while True:
            found = _cookies_from_list(await context.cookies([base_url]))
            if found is not None:
                return found
            if asyncio.get_running_loop().time() >= deadline:
                raise AuthError('Planfix login timed out waiting for session cookies')
            await asyncio.sleep(0.05)

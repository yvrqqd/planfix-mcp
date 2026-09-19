from pathlib import Path

from planfix_mcp.errors import AuthError


def launch_kwargs(browser_bin: str = '', *, headless: bool = True) -> dict[str, object]:
    return {
        'headless': headless,
        'executable_path': str(resolve_browser(browser_bin)),
    }


def resolve_browser(browser_bin: str = '') -> Path:
    if browser_bin:
        path = Path(browser_bin)
        if not path.is_file():
            raise AuthError('PF_BROWSER_BIN does not point to a browser executable')
        return path
    path = _bundled_chromium_path()
    if not path.is_file():
        raise AuthError(
            'Playwright Chromium is not installed; run "python -m playwright install chromium" during setup',
        )
    return path


def _bundled_chromium_path() -> Path:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        return Path(playwright.chromium.executable_path)

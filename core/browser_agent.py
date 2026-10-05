"""Verified DOM operations using the existing Playwright session owner."""
from urllib.parse import urlparse


async def perform_on_page(action, page):
    kind = action.type.value
    timeout = int(action.timeout * 1000)
    if kind == "BrowserNavigate":
        if urlparse(action.target).scheme not in ("http", "https"):
            raise ValueError("Only HTTP(S) browser navigation is supported.")
        response = await page.goto(action.target, wait_until="domcontentloaded", timeout=timeout)
        verified = page.url.rstrip("/") == action.target.rstrip("/") and (response is None or response.ok)
        return {"verified": verified, "message": "Navigation verified." if verified else "Navigation redirected or failed; inspect the page."}
    source_url = action.arguments.get("source_url")
    if not source_url or page.url != source_url:
        raise ValueError("The browser page changed. Observe its URL before acting.")
    locator = page.locator(action.target)
    if await locator.count() != 1:
        raise ValueError("The browser target is missing or ambiguous. Choose one unique element.")
    if not await locator.is_visible() or not await locator.is_enabled():
        raise ValueError("The browser target is not visible and enabled.")
    if (await locator.get_attribute("type") or "").lower() == "password":
        raise PermissionError("Protected fields cannot be automated.")
    if kind == "BrowserType":
        await locator.fill(action.arguments["text"], timeout=timeout)
        verified = await locator.input_value(timeout=timeout) == action.arguments["text"]
    elif kind == "BrowserClick":
        if action.verification not in ("url_equals", "element_present") or not action.expected_result:
            raise ValueError("Browser clicks require a destination URL or visible selector postcondition.")
        await locator.click(timeout=timeout)
        if action.verification == "url_equals":
            await page.wait_for_url(action.expected_result, timeout=timeout)
            verified = page.url == action.expected_result
        else:
            expected = page.locator(action.expected_result)
            await expected.wait_for(state="visible", timeout=timeout)
            verified = await expected.count() == 1 and await expected.is_visible()
    else:
        raise ValueError("Unsupported browser action.")
    return {"verified": verified, "message": "Browser result verified." if verified else "Browser result not verified."}


def perform(action, context):
    from actions.browser_control import _registry
    browser = action.arguments.get("browser")
    if action.type.value != "BrowserNavigate" and not _registry.has(browser):
        raise ValueError("No managed browser session. Navigate with BrowserNavigate first.")
    session = _registry.get(browser)
    async def run():
        page = await session._get_page()
        from core.agent_runtime import get_runtime
        title = await page.title()
        if get_runtime().screen.policy.blocked(context.active_process, title):
            raise PermissionError("The browser page is excluded from screen sharing.")
        if action.type.value != "BrowserNavigate" and (
                not title or title.casefold() not in context.active_window_title.casefold()):
            raise ValueError("The managed browser page is not the shared window. Focus it before acting.")
        return await perform_on_page(action, page)
    return session.run(run(), timeout=action.timeout)

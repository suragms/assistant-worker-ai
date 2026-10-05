import asyncio
import pytest
from core.agent_actions import Action, ActionType
from core.browser_agent import perform_on_page


def test_real_dom_unique_targets_password_and_verification():
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.launch(headless=True)
            except Exception as exc:
                pytest.skip(f"Playwright Chromium unavailable: {type(exc).__name__}")
            try:
                page = await browser.new_page()
                await page.set_content('<button onclick="document.querySelector(\'p\').hidden=false">Continue</button><p hidden>Done</p><input id="text"><input id="secret" type="password"><a>Repeated</a><a>Repeated</a>')
                args = {"source_url": "about:blank"}
                result = await perform_on_page(Action(ActionType.BrowserClick, "button", args,
                                                     verification="element_present", expected_result="p"), page)
                assert result["verified"]
                result = await perform_on_page(Action(ActionType.BrowserType, "#text", dict(args, text="literal {ENTER}")), page)
                assert result["verified"]
                with pytest.raises(ValueError, match="ambiguous"):
                    await perform_on_page(Action(ActionType.BrowserClick, "a", args), page)
                with pytest.raises(PermissionError):
                    await perform_on_page(Action(ActionType.BrowserType, "#secret", dict(args, text="value")), page)
                with pytest.raises(ValueError, match="page changed"):
                    await perform_on_page(Action(ActionType.BrowserClick, "button", {"source_url": "https://wrong.invalid"}), page)
            finally:
                await browser.close()
    asyncio.run(run())

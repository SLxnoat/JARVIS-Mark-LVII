"""
Inbuilt HUD Browser Plugin for JARVIS Mark LVII.

Powered by Playwright Chromium Engine. Allows JARVIS to navigate websites,
inspect local web development servers (localhost:3000, localhost:8000), click
elements, type inputs, scroll, read DOM articles, and stream high-resolution
viewport frames directly into the center avatar HUD surface via player.show_image().

Restores the 8,000-particle cybernetic hologram avatar cleanly via player.stop_video()
upon closing.
"""

from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

# Attempt Playwright import
try:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = Any  # type: ignore
    BrowserContext = Any  # type: ignore
    Page = Any  # type: ignore
    Playwright = Any  # type: ignore


PLUGIN_NAME = "inbuilt_hud_browser"

PLUGIN = {
    "name": PLUGIN_NAME,
    "description": (
        "Inbuilt Playwright web browser engine with live HUD avatar projection. "
        "Allows JARVIS to navigate to web addresses (including localhost dev servers), "
        "click buttons, type into search inputs, scroll pages, extract article content, "
        "and project live rendered viewport frames directly into the center HUD display. "
        "Trigger phrases: 'open website on hud', 'browse to <url>', 'show web page', "
        "'click <element>', 'scroll down the page', 'read web page', 'close the browser'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Action to perform: 'open' (navigate to URL and project onto HUD), "
                    "'click' (click element by text or CSS selector), "
                    "'type' (fill text into an input field), "
                    "'scroll' (scroll down, up, top, or bottom), "
                    "'read_content' (extract readable text and headings to content panel), "
                    "'screenshot' (refresh HUD viewport frame capture), "
                    "'close' (close browser and restore cybernetic hologram avatar)."
                ),
                "enum": ["open", "click", "type", "scroll", "read_content", "screenshot", "close"],
            },
            "url": {
                "type": "STRING",
                "description": "Website or local server URL (e.g. 'https://news.ycombinator.com', 'http://localhost:8000/docs').",
            },
            "selector": {
                "type": "STRING",
                "description": "CSS selector or element text to target (e.g. 'input[name=q]', 'text=Sign In', 'button.submit').",
            },
            "text": {
                "type": "STRING",
                "description": "Text to enter into the input field for 'type' action.",
            },
            "direction": {
                "type": "STRING",
                "description": "Scroll direction: 'down', 'up', 'top', or 'bottom' (default 'down').",
                "enum": ["down", "up", "top", "bottom"],
            },
            "scroll_amount": {
                "type": "INTEGER",
                "description": "Scroll distance in pixels (default 600).",
            },
        },
        "required": ["action"],
    },
    "PLUGIN_SETTINGS": {
        "viewport_width": 1024,
        "viewport_height": 640,
        "color_scheme": "dark",
        "default_scroll": 600,
        "navigation_timeout_ms": 15000,
    },
}

SCREENSHOT_PATH = Path(__file__).resolve().parent.parent / "screenshots" / "hud_browser_viewport.png"


class BrowserSessionManager:
    """Singleton managing Playwright Chromium instance inside a background daemon thread."""

    _instance: Optional[BrowserSessionManager] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._ready_event = threading.Event()
        self._start_thread()

    @classmethod
    def get_instance(cls) -> BrowserSessionManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = BrowserSessionManager()
            return cls._instance

    def _start_thread(self) -> None:
        if self.thread and self.thread.is_alive():
            return

        def _runner():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self._ready_event.set()
            self.loop.run_forever()

        self._thread = threading.Thread(target=_runner, name="HUDPlaywrightThread", daemon=True)
        self._thread.start()
        self._ready_event.wait(timeout=5.0)

    def _run_coroutine(self, coro, timeout: float = 25.0) -> Any:
        if not self.loop or not self.loop.is_running():
            self._ready_event.clear()
            self._start_thread()

        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=timeout)

    async def _async_ensure_page(self) -> Page:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright is not installed in the current environment.")

        if self._pw is None:
            self._pw = await async_playwright().start()

        if self._browser is None:
            self._browser = await self._pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )

        if self._context is None:
            self._context = await self._browser.new_context(
                viewport={"width": 1024, "height": 640},
                color_scheme="dark",
                user_agent="Mozilla/5.0 (X11; Linux x86_64) JARVIS-HUD/1.0 (Cybernetic Avatar Browser)",
                ignore_https_errors=True,
            )

        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()

        return self._page

    async def _async_capture_frame(self, page: Page) -> str:
        SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(SCREENSHOT_PATH), full_page=False)
        return str(SCREENSHOT_PATH.resolve())

    async def _async_navigate(self, url: str, timeout_ms: int = 15000) -> Dict[str, Any]:
        page = await self._async_ensure_page()
        # Clean URL
        target_url = url.strip()
        if not (target_url.startswith("http://") or target_url.startswith("https://") or target_url.startswith("file://")):
            if target_url.startswith("localhost") or target_url.startswith("127.0.0.1"):
                target_url = f"http://{target_url}"
            else:
                target_url = f"https://{target_url}"

        await page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
        title = await page.title()
        screenshot_path = await self._async_capture_frame(page)
        return {
            "title": title or target_url,
            "url": page.url,
            "screenshot": screenshot_path,
        }

    async def _async_click(self, selector: str, timeout_ms: int = 8000) -> Dict[str, Any]:
        page = await self._async_ensure_page()
        await page.click(selector, timeout=timeout_ms)
        await page.wait_for_timeout(600)
        title = await page.title()
        screenshot_path = await self._async_capture_frame(page)
        return {
            "title": title or page.url,
            "url": page.url,
            "screenshot": screenshot_path,
        }

    async def _async_type(self, selector: str, text: str, timeout_ms: int = 8000) -> Dict[str, Any]:
        page = await self._async_ensure_page()
        if selector:
            await page.fill(selector, text, timeout=timeout_ms)
        else:
            await page.keyboard.type(text)
        await page.wait_for_timeout(400)
        title = await page.title()
        screenshot_path = await self._async_capture_frame(page)
        return {
            "title": title or page.url,
            "url": page.url,
            "screenshot": screenshot_path,
        }

    async def _async_scroll(self, direction: str = "down", amount: int = 600) -> Dict[str, Any]:
        page = await self._async_ensure_page()
        direction_lower = direction.lower().strip()
        if direction_lower == "up":
            await page.evaluate(f"window.scrollBy(0, -{amount});")
        elif direction_lower == "top":
            await page.evaluate("window.scrollTo(0, 0);")
        elif direction_lower == "bottom":
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        else:
            await page.evaluate(f"window.scrollBy(0, {amount});")

        await page.wait_for_timeout(300)
        title = await page.title()
        screenshot_path = await self._async_capture_frame(page)
        return {
            "title": title or page.url,
            "url": page.url,
            "screenshot": screenshot_path,
        }

    async def _async_screenshot(self) -> Dict[str, Any]:
        page = await self._async_ensure_page()
        title = await page.title()
        screenshot_path = await self._async_capture_frame(page)
        return {
            "title": title or page.url,
            "url": page.url,
            "screenshot": screenshot_path,
        }

    async def _async_extract_content(self) -> Dict[str, Any]:
        page = await self._async_ensure_page()
        extracted = await page.evaluate(
            """() => {
                const title = document.title || "";
                const headings = Array.from(document.querySelectorAll("h1, h2, h3"))
                                      .map(h => `${h.tagName}: ${h.innerText.trim()}`)
                                      .filter(t => t.length > 5)
                                      .slice(0, 10);
                const paragraphs = Array.from(document.querySelectorAll("p, article, li"))
                                        .map(p => p.innerText.trim())
                                        .filter(t => t.length > 25)
                                        .slice(0, 12);
                return {
                    title: title,
                    headings: headings,
                    paragraphs: paragraphs,
                    url: window.location.href
                };
            }"""
        )
        title = extracted.get("title", "Web Page")
        url = extracted.get("url", page.url)
        headings = extracted.get("headings", [])
        paragraphs = extracted.get("paragraphs", [])

        # Build clean markdown
        md_lines = [f"# {title}", f"**URL:** {url}\n"]
        if headings:
            md_lines.append("### Key Sections:")
            for h in headings:
                md_lines.append(f"- {h}")
            md_lines.append("")

        if paragraphs:
            md_lines.append("### Content Summary:")
            for p in paragraphs:
                md_lines.append(f"> {p}\n")

        markdown_body = "\n".join(md_lines)
        spoken_sample = paragraphs[0] if paragraphs else "No detailed text paragraphs found."
        if len(spoken_sample) > 160:
            spoken_sample = spoken_sample[:157] + "..."

        spoken_summary = (
            f"Extracted content from {title}. Top summary: {spoken_sample}. "
            "Full structural content displayed on your content panel, sir."
        )

        return {
            "title": title,
            "url": url,
            "markdown": markdown_body,
            "spoken_summary": spoken_summary,
        }

    async def _async_close(self) -> None:
        if self._page and not self._page.is_closed():
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None

        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
            self._pw = None

    def navigate(self, url: str, timeout_ms: int = 15000) -> Dict[str, Any]:
        return self._run_coroutine(self._async_navigate(url, timeout_ms), timeout=timeout_ms / 1000.0 + 8.0)

    def click_element(self, selector: str, timeout_ms: int = 8000) -> Dict[str, Any]:
        return self._run_coroutine(self._async_click(selector, timeout_ms), timeout=timeout_ms / 1000.0 + 8.0)

    def type_text(self, selector: str, text: str, timeout_ms: int = 8000) -> Dict[str, Any]:
        return self._run_coroutine(self._async_type(selector, text, timeout_ms), timeout=timeout_ms / 1000.0 + 8.0)

    def scroll_page(self, direction: str = "down", amount: int = 600) -> Dict[str, Any]:
        return self._run_coroutine(self._async_scroll(direction, amount), timeout=10.0)

    def screenshot(self) -> Dict[str, Any]:
        return self._run_coroutine(self._async_screenshot(), timeout=10.0)

    def extract_content(self) -> Dict[str, Any]:
        return self._run_coroutine(self._async_extract_content(), timeout=12.0)

    def close(self) -> None:
        self._run_coroutine(self._async_close(), timeout=10.0)


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Execute HUD browser action and project frames to avatar HUD display."""
    if not PLAYWRIGHT_AVAILABLE:
        return (
            "Playwright browser engine is not installed in the JARVIS environment. "
            "Please install Playwright with 'pip install playwright' and 'playwright install chromium'."
        )

    action = parameters.get("action", "").lower().strip()
    if not action:
        return "Please specify an action for the HUD browser (e.g., 'open', 'click', 'scroll', 'close')."

    manager = BrowserSessionManager.get_instance()

    try:
        if action == "open":
            url = parameters.get("url") or "https://news.ycombinator.com"
            res = manager.navigate(url)
            page_title = res.get("title", url)
            screenshot_path = res.get("screenshot")

            if player:
                if hasattr(player, "show_image") and screenshot_path:
                    player.show_image(screenshot_path, title=f"HUD Web: {page_title[:35]}")
                    if hasattr(player, "show_browser_viewport"):
                        player.show_browser_viewport(screenshot_path, url=res.get("url", "") if isinstance(res, dict) else "")
                if hasattr(player, "write_log"):
                    player.write_log(f"[HUD Browser] Opened {res.get('url')} ({page_title})")

            return f"Displaying {page_title} on the HUD, sir."

        elif action == "click":
            selector = parameters.get("selector", "").strip()
            if not selector:
                return "Please specify the link text or selector to click on the HUD browser, sir."

            res = manager.click_element(selector)
            page_title = res.get("title", "")
            screenshot_path = res.get("screenshot")

            if player:
                if hasattr(player, "show_image") and screenshot_path:
                    player.show_image(screenshot_path, title=f"HUD Web: {page_title[:35]}")
                    if hasattr(player, "show_browser_viewport"):
                        player.show_browser_viewport(screenshot_path, url=res.get("url", "") if isinstance(res, dict) else "")
                if hasattr(player, "write_log"):
                    player.write_log(f"[HUD Browser] Clicked '{selector}'")

            return f"Clicked '{selector}' on the HUD browser, sir."

        elif action == "type":
            selector = parameters.get("selector", "").strip()
            text = parameters.get("text", "")
            if not text:
                return "Please specify the text you would like me to enter, sir."

            res = manager.type_text(selector, text)
            page_title = res.get("title", "")
            screenshot_path = res.get("screenshot")

            if player:
                if hasattr(player, "show_image") and screenshot_path:
                    player.show_image(screenshot_path, title=f"HUD Web: {page_title[:35]}")
                    if hasattr(player, "show_browser_viewport"):
                        player.show_browser_viewport(screenshot_path, url=res.get("url", "") if isinstance(res, dict) else "")
                if hasattr(player, "write_log"):
                    player.write_log(f"[HUD Browser] Typed '{text}' into '{selector or 'active element'}'")

            target_name = f"'{selector}'" if selector else "the active field"
            return f"Entered text into {target_name} on the HUD browser, sir."

        elif action == "scroll":
            direction = parameters.get("direction", "down")
            amount = int(parameters.get("scroll_amount") or 600)

            res = manager.scroll_page(direction=direction, amount=amount)
            page_title = res.get("title", "")
            screenshot_path = res.get("screenshot")

            if player:
                if hasattr(player, "show_image") and screenshot_path:
                    player.show_image(screenshot_path, title=f"HUD Web: {page_title[:35]}")
                    if hasattr(player, "show_browser_viewport"):
                        player.show_browser_viewport(screenshot_path, url=res.get("url", "") if isinstance(res, dict) else "")
                if hasattr(player, "write_log"):
                    player.write_log(f"[HUD Browser] Scrolled {direction} by {amount}px")

            return f"Scrolled {direction} on the HUD browser, sir."

        elif action == "read_content":
            res = manager.extract_content()
            title = res.get("title", "Web Page")
            markdown = res.get("markdown", "")
            spoken = res.get("spoken_summary", f"Extracted content from {title}.")

            if player:
                if hasattr(player, "show_content") and markdown:
                    player.show_content(f"HUD Browser: {title}", markdown)
                if hasattr(player, "write_log"):
                    player.write_log(f"[HUD Browser] Extracted readable content from {title}")

            return spoken

        elif action == "screenshot":
            res = manager.screenshot()
            page_title = res.get("title", "")
            screenshot_path = res.get("screenshot")

            if player:
                if hasattr(player, "show_image") and screenshot_path:
                    player.show_image(screenshot_path, title=f"HUD Web: {page_title[:35]}")
                    if hasattr(player, "show_browser_viewport"):
                        player.show_browser_viewport(screenshot_path, url=res.get("url", "") if isinstance(res, dict) else "")
                if hasattr(player, "write_log"):
                    player.write_log("[HUD Browser] Refreshed HUD viewport frame")

            return "HUD browser frame refreshed, sir."

        elif action == "close":
            manager.close()

            if player:
                if hasattr(player, "stop_video"):
                    # Closes image surface and restores the 8K cybernetic hologram avatar
                    player.stop_video()
                if hasattr(player, "write_log"):
                    player.write_log("[HUD Browser] Closed session; cybernetic avatar restored.")

            return "Browser session closed. Restoring avatar, sir."

        else:
            return f"Unrecognized HUD browser action '{action}'. Valid actions: open, click, type, scroll, read_content, screenshot, close."

    except Exception as exc:
        err_msg = str(exc)
        if player and hasattr(player, "write_log"):
            player.write_log(f"[HUD Browser Error] {err_msg}")
        return f"HUD browser encountered an issue while performing '{action}': {err_msg}"

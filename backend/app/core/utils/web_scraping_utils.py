from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
import httpx

async def fetch_from_url(
    url: str,
    headers: dict[str, str] | None = None,
    use_http_request: bool = False,
) -> str:
    """Fetch URL content using Playwright by default, or httpx when requested."""
    if use_http_request:
        default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        }
        # Merge custom headers with default headers (custom headers override defaults)
        headers = {**default_headers, **(headers or {})}

        async with httpx.AsyncClient(
                follow_redirects=True,
                headers=headers
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to the URL
        await page.goto(url, wait_until="domcontentloaded")

        # Get the HTML content
        html = await page.content()

        await browser.close()
        return html

def html2text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # Remove script/style
    for bad in soup(["script", "style", "noscript"]):
        bad.extract()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n\s*\n", "\n\n", text)  # squeeze blank lines
    return text.strip()

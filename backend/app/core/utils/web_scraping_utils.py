from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re


async def fetch_from_url(url: str) -> str:
    """Fetch URL content using a real browser (Playwright)."""
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

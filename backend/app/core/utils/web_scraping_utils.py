import httpx
from bs4 import BeautifulSoup
import re


async def fetch_from_url(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    async with httpx.AsyncClient(
        follow_redirects=True,
        headers=headers
    ) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text


def html2text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # Remove script/style
    for bad in soup(["script", "style", "noscript"]):
        bad.extract()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n\s*\n", "\n\n", text)  # squeeze blank lines
    return text.strip()
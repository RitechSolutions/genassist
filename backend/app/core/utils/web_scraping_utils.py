import httpx
from bs4 import BeautifulSoup
import re


async def fetch_from_url(url: str) -> str:
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
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

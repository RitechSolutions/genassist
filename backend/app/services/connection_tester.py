import httpx


async def test_zendesk(cd: dict) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://{cd['subdomain']}.zendesk.com/api/v2/users/me.json",
            auth=(f"{cd['email']}/token", cd["api_token"]),
            timeout=10.0,
        )
        response.raise_for_status()
    return {"success": True, "message": "Successfully connected to Zendesk."}


async def test_url(cd: dict) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(cd["url"], timeout=10.0, follow_redirects=True)
        response.raise_for_status()
    return {"success": True, "message": "URL is accessible."}

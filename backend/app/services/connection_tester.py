import httpx


async def test_zendesk(cd: dict) -> dict:
    async with httpx.AsyncClient() as client:
        # check if subdomain has also the zendesk.com domain
        if not cd["subdomain"].endswith(".zendesk.com"):
            cd["subdomain"] = f"{cd['subdomain']}.zendesk.com"
        else:
            cd["subdomain"] = cd["subdomain"]

        url = f"https://{cd['subdomain']}/api/v2/users/me.json"

        response = await client.get(
            url,
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

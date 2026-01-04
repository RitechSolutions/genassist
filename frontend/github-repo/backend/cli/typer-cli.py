import json
import requests
import typer
from pathlib import Path

app = typer.Typer()

DEFAULT_BASE_URL = "http://localhost:8000"

@app.command("call-api")
def call_api(
    endpoint: str = typer.Argument(
        ...,
        help="Path part of the endpoint, e.g. 'api/audio/metrics'"
    ),
    url: str = typer.Option(
        DEFAULT_BASE_URL,
        "-u", "--url",
        help="Base URL of the FastAPI server.",
        show_default=True,
    ),
    token: str | None = typer.Option(
        None,
        "-t", "--token",
        envvar="API_TOKEN",
        help="Bearer token for the Authorization header.",
    ),
    header: list[str] = typer.Option(
        [],
        "-H", "--header",
        help="Extra HTTP header(s) in KEY:VALUE format. Repeat for multiple headers.",
    ),
    data: str | None = typer.Option(
        None,
        "-d", "--data",
        help="Inline JSON string to send as the request body.",
    ),
    data_file: Path | None = typer.Option(
        None,
        "--data-file",
        help="Path to a JSON file to send as the request body.",
    ),
    method: str | None = typer.Option(
        None,
        "-X", "--method",
        help="HTTP verb to use (GET, POST, PUT, PATCH, DELETE …). "
             "If omitted, POST is used when a body is supplied, otherwise GET.",
    ),
):
    """
    Call a FastAPI endpoint, optionally sending a JSON body.
    """
    # ---------- decide HTTP verb ----------
    verb = (method or ("POST" if (data or data_file) else "GET")).upper()

    # ---------- build headers ----------
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for h in header:
        key, _, value = h.partition(":")
        if not _:
            typer.secho(f"Ignoring malformed header: {h}", fg=typer.colors.RED)
            continue
        headers[key.strip()] = value.strip()

    # ---------- assemble payload ----------
    payload = None
    try:
        if data_file:
            payload = json.load(data_file.open())
        elif data:
            payload = json.loads(data)
    except json.JSONDecodeError as exc:
        typer.secho(f"Invalid JSON supplied: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # ---------- send request ----------
    full = f"{url.rstrip('/')}/{endpoint.lstrip('/')}"
    typer.echo(f"➡️  {verb} {full}")

    try:
        r = requests.request(verb, full, headers=headers, json=payload)
        typer.echo(f"Status: {r.status_code}")
        if r.headers.get("content-type", "").startswith("application/json"):
            typer.echo(r.json())
        else:
            typer.echo(r.text)
    except Exception as exc:
        typer.secho(f"❌  {exc}", fg=typer.colors.RED)


if __name__ == "__main__":
    app()

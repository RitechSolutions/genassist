"""Bedrock embedder closes each connection after its answer and bounds its AWS connect time."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import boto3
import pytest

from app.modules.data.providers.vector.embedding import bedrock
from app.modules.data.providers.vector.embedding.base import EmbeddingConfig
from app.modules.data.providers.vector.embedding.bedrock import BedrockEmbedder


class _TitanStub(BaseHTTPRequestHandler):
    """Answers like Bedrock, including confirming a requested close."""

    protocol_version = "HTTP/1.1"

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.request_headers.append(dict(self.headers))
        body = json.dumps({"embedding": [0.1, 0.2], "inputTextTokenCount": 1}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if self.headers.get("Connection", "").lower() == "close":
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _CountingServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _TitanStub)
        self.request_headers = []
        self.connections = 0

    def get_request(self):
        accepted = super().get_request()
        self.connections += 1
        return accepted


@pytest.fixture
def isolated_aws_env(monkeypatch):
    """Fake keys and a fresh default boto3 session so nothing leaks into or out of these tests."""
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", None)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    for name in ("AWS_SESSION_TOKEN", "AWS_PROFILE", "AWS_DEFAULT_PROFILE", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def titan_stub(isolated_aws_env, monkeypatch):
    server = _CountingServer()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("AWS_ENDPOINT_URL_BEDROCK_RUNTIME", f"http://127.0.0.1:{server.server_address[1]}")
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def embedder(isolated_aws_env, monkeypatch):
    monkeypatch.setattr(bedrock.settings, "BEDROCK_TIMEOUT_QUERY_EMBEDDING_SECONDS", 5)
    return BedrockEmbedder(EmbeddingConfig(type="bedrock", model_id="amazon.titan-embed-text-v2:0"))


@pytest.mark.asyncio
async def test_each_search_opens_its_own_connection(titan_stub, embedder):
    assert await embedder.initialize()

    assert await embedder.embed_query("first") == [0.1, 0.2]
    assert await embedder.embed_query("second") == [0.1, 0.2]

    assert titan_stub.connections == 2


@pytest.mark.asyncio
async def test_close_is_requested_and_left_out_of_the_signature(titan_stub, embedder):
    assert await embedder.initialize()

    assert await embedder.embed_texts(["chunk"]) == [[0.1, 0.2]]

    headers = titan_stub.request_headers[0]
    signed_headers_part = headers["Authorization"].split("SignedHeaders=")[1]
    signed_headers = signed_headers_part.split(",")[0].split(";")
    assert headers["Connection"] == "close"
    assert "connection" not in signed_headers


@pytest.mark.asyncio
async def test_connect_limit_follows_the_embedding_timeout_and_read_limit_is_unchanged(embedder):
    assert await embedder.initialize()

    client_config = embedder.client.client.meta.config

    assert client_config.connect_timeout == 5
    assert client_config.read_timeout == 60

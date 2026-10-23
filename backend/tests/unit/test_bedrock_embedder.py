"""Bedrock embedder never reuses an idle connection: searches close after each answer, batches drop theirs."""
import asyncio
import gc
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import boto3
import pytest

from app.modules.data.providers.vector.embedding import bedrock
from app.modules.data.providers.vector.embedding.base import EmbeddingConfig
from app.modules.data.providers.vector.embedding.bedrock import BedrockEmbedder

PARALLEL_REQUESTS = 4


class _TitanStub(BaseHTTPRequestHandler):
    """Answers like Bedrock, confirms a requested close and rejects texts starting with 'reject'."""

    protocol_version = "HTTP/1.1"

    def do_POST(self):
        text = self._read_text()
        self.server.record(self.client_address[1], text, dict(self.headers))
        if text.startswith("reject"):
            self._respond(400, {"message": "rejected"}, error_type="ValidationException")
        else:
            self._respond(200, {"embedding": [0.1, 0.2], "inputTextTokenCount": 1})

    def _read_text(self):
        content_length = int(self.headers.get("Content-Length", 0))
        request_body = json.loads(self.rfile.read(content_length))
        return request_body["inputText"]

    def _respond(self, status, payload, error_type=None):
        body = json.dumps(payload).encode()
        close_requested = self.headers.get("Connection", "").lower() == "close"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if error_type:
            self.send_header("x-amzn-ErrorType", error_type)
        if close_requested:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _CountingServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _TitanStub)
        self.requests = []
        self.connections = 0
        self.open_connections = 0
        self.closed_ports = set()
        self._lock = threading.Lock()

    def record(self, client_port, text, headers):
        with self._lock:
            self.requests.append({"port": client_port, "text": text, "headers": headers})

    def get_request(self):
        accepted = super().get_request()
        with self._lock:
            self.connections += 1
            self.open_connections += 1
        return accepted

    def finish_request(self, request, client_address):
        super().finish_request(request, client_address)
        with self._lock:
            self.open_connections -= 1
            self.closed_ports.add(client_address[1])


async def _wait_until(condition, description, seconds=3.0):
    for _ in range(int(seconds / 0.05)):
        gc.collect()
        if condition():
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"Timed out after {seconds} s waiting until {description}")


def _limit_parallel_requests():
    asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS))


@pytest.fixture
def isolated_aws_env(monkeypatch):
    """Fake keys and a fresh default boto3 session so nothing leaks into or out of these tests."""
    monkeypatch.setattr(boto3, "DEFAULT_SESSION", None)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("AWS_CONFIG_FILE", os.devnull)
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", os.devnull)
    for name in ("AWS_SESSION_TOKEN", "AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_IGNORE_CONFIGURED_ENDPOINT_URLS",
                 "HTTP_PROXY", "http_proxy"):
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
async def test_search_asks_to_close_and_keeps_it_out_of_the_signature(titan_stub, embedder):
    assert await embedder.initialize()

    assert await embedder.embed_query("question") == [0.1, 0.2]

    headers = titan_stub.requests[0]["headers"]
    signed_headers_part = headers["Authorization"].split("SignedHeaders=")[1]
    signed_headers = signed_headers_part.split(",")[0].split(";")
    assert headers["Connection"] == "close"
    assert "connection" not in signed_headers


@pytest.mark.asyncio
async def test_batch_reuses_connections_and_leaves_none_open(titan_stub, embedder):
    _limit_parallel_requests()
    assert await embedder.initialize()
    chunks = [f"chunk {number}" for number in range(30)]

    embeddings = await embedder.embed_texts(chunks)
    await _wait_until(lambda: titan_stub.open_connections == 0, "the batch's connections are closed")

    batch_asked_to_close = any(request["headers"].get("Connection") == "close" for request in titan_stub.requests)
    assert len(embeddings) == len(chunks)
    assert titan_stub.connections <= PARALLEL_REQUESTS
    assert not batch_asked_to_close
    assert titan_stub.open_connections == 0


@pytest.mark.asyncio
async def test_batch_after_a_failed_batch_uses_only_new_connections(titan_stub, embedder):
    _limit_parallel_requests()
    assert await embedder.initialize()
    failing_batch = ["reject this chunk"] + [f"chunk {number}" for number in range(29)]

    assert await embedder.embed_texts(failing_batch) == []
    await _wait_until(lambda: len(titan_stub.requests) == len(failing_batch), "the failed batch's requests all arrive")
    ports_used_before = {request["port"] for request in titan_stub.requests}

    embeddings = await embedder.embed_texts([f"chunk {number}" for number in range(30)])
    ports_used_after = {request["port"] for request in titan_stub.requests[len(failing_batch):]}
    await _wait_until(lambda: ports_used_after <= titan_stub.closed_ports, "the second batch's connections are closed")

    assert len(embeddings) == 30
    assert ports_used_after.isdisjoint(ports_used_before)
    assert ports_used_after <= titan_stub.closed_ports


@pytest.mark.asyncio
async def test_no_client_is_built_per_batch(titan_stub, embedder, monkeypatch):
    assert await embedder.initialize()
    builds = []
    monkeypatch.setattr(embedder, "_build_client", lambda **kwargs: builds.append(kwargs))

    for _ in range(3):
        assert await embedder.embed_texts(["first chunk", "second chunk"]) == [[0.1, 0.2], [0.1, 0.2]]

    assert builds == []


@pytest.mark.asyncio
async def test_reinitialize_rebuilds_only_the_search_client(embedder):
    assert await embedder.initialize()
    search_client, batch_client = embedder.client, embedder._batch_client

    assert await embedder.initialize()

    assert embedder.client is not search_client
    assert embedder._batch_client is batch_client


@pytest.mark.asyncio
async def test_failed_setup_saves_neither_client(embedder, monkeypatch):
    build_client = embedder._build_client

    def fail_for_batch_client(close_after_each_call):
        if not close_after_each_call:
            raise RuntimeError("batch client unavailable")
        return build_client(close_after_each_call=close_after_each_call)

    monkeypatch.setattr(embedder, "_build_client", fail_for_batch_client)

    assert not await embedder.initialize()
    assert embedder.client is None
    assert embedder._batch_client is None


@pytest.mark.asyncio
async def test_knowledge_base_timeouts_are_used_when_set(isolated_aws_env):
    config = EmbeddingConfig(type="bedrock", model_id="amazon.titan-embed-text-v2:0", connect_timeout=3, read_timeout=20)
    embedder = BedrockEmbedder(config)

    assert await embedder.initialize()

    for client in (embedder.client, embedder._batch_client):
        client_config = client.client.meta.config
        assert client_config.connect_timeout == 3
        assert client_config.read_timeout == 20


@pytest.mark.asyncio
async def test_connect_limit_follows_the_embedding_timeout_and_read_limit_is_unchanged(embedder):
    assert await embedder.initialize()

    for client in (embedder.client, embedder._batch_client):
        client_config = client.client.meta.config
        assert client_config.connect_timeout == 5
        assert client_config.read_timeout == 60

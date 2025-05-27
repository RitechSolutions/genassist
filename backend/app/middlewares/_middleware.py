from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette_context.middleware import RawContextMiddleware
from starlette_context.plugins import RequestIdPlugin

from app.core.config.logging import RequestContextMiddleware


ALLOWED_ORIGINS = [
    "http://localhost",
    "https://localhost",
    "http://localhost:8080",
    "https://localhost:8080",
    "http://localhost:8081",
    "http://localhost:8081",
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:8080",
    "https://127.0.0.1:8080",
    "http://0.0.0.0:3000",
    "https://0.0.0.0:3000",
    "http://0.0.0.0:8080",
    "https://0.0.0.0:8080",
    "https://genassist.ritech.io",
    "https://genassist-dev.ritech.io",
    "https://genassist-test.ritech.io",
    "https://genassist.ritech.io",
]


def build_middlewares() -> list[Middleware]:
    """
    Middlewares that must run **before** user-code.
    Order matters:

    1. RawContextMiddleware – creates `starlette_context` and the X-Request-ID header.
    2. RequestContextMiddleware – copies data into the Loguru ContextVars and
       times the request.
    3. CORS – normal cross-origin checks.
    """
    return [
        # 1️⃣  Generates a request-scoped UUID and puts it in `request.headers`
        Middleware(
            RawContextMiddleware,
            plugins=(RequestIdPlugin(),),
        ),
        # 2️⃣  Fills Loguru context vars, measures duration, etc.
        Middleware(RequestContextMiddleware),
        # 3️⃣  CORS
        Middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ]

import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from config import settings
from auth.token_verifier import TokenVerifier
from connections.manager import ConnectionManager
from heartbeat.ping_pong import heartbeat_loop
from redis_relay.publisher import RedisPublisher
from redis_relay.subscriber import RedisSubscriber
from routes import conversations, dashboard, health, twilio, voice

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting websocket service...")

    # Initialize Redis
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis_client.ping()
    logger.info("Redis connected")

    # Initialize components
    manager = ConnectionManager()
    verifier = TokenVerifier()
    subscriber = RedisSubscriber(redis_client, manager)
    publisher = RedisPublisher(redis_client)

    # Start background tasks
    await verifier.start()
    await subscriber.start()
    heartbeat_task = asyncio.create_task(heartbeat_loop(manager))

    # Attach to app state for route access
    app.state.manager = manager
    app.state.verifier = verifier
    app.state.publisher = publisher
    app.state.redis = redis_client

    logger.info(f"websocket service ready on port {settings.WS_PORT}")

    try:
        yield
    finally:
        logger.info("Shutting down websocket service...")

        # Cancel heartbeat
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        # Stop subscriber and verifier
        await subscriber.stop()
        await verifier.stop()

        # Close Redis
        await redis_client.close()
        logger.info("websocket service shutdown complete")


app = FastAPI(
    title="GenAssist WebSocket Service",
    lifespan=lifespan,
)

# Register routes
app.include_router(health.router)
app.include_router(conversations.router, prefix="/ws")
app.include_router(dashboard.router, prefix="/ws")
app.include_router(voice.router, prefix="/ws")
app.include_router(twilio.router, prefix="/ws")

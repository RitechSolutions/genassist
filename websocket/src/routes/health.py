from fastapi import APIRouter, Request, WebSocket

router = APIRouter()


@router.get("/health")
async def health():
    return {"service": "websocket", "status": "ok"}


@router.get("/ready")
async def ready(request: Request):
    manager = request.app.state.manager
    stats = manager.get_stats()
    return {"service": "websocket", "status": "ready", **stats}


# add a test websocket route to test the websocket connection
@router.websocket("/test")
async def test(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("WebSocket connection established!")
    await websocket.close()

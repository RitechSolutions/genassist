from app.api.v1.routes import router


def register_routers(app):
    app.include_router(router, prefix="/api", tags=["v1"])

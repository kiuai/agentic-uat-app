from fastapi import FastAPI
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import auth as auth_routes
from app.routes import admin as admin_routes
from app.routes import core as core_routes
from app.routes import jobs as jobs_routes
from app.routes import ui as ui_routes
from app.db import SessionLocal
from app.startup import ensure_roles, ensure_admin
from app.settings import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        ensure_roles(db)
        ensure_admin(db)
    finally:
        db.close()
    yield

app = FastAPI(title="Agentic UAT App", version="0.1.0", lifespan=lifespan)

# Session cookie for the UI (separate from API JWT usage)
app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key, https_only=False)

app.mount("/ui/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(core_routes.router)
app.include_router(jobs_routes.router)
app.include_router(ui_routes.router)

@app.get("/")
def root():
    return {"name": "Agentic UAT App", "docs": "/docs", "ui": "/ui"}

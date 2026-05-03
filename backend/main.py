"""
TG-Shop  |  FastAPI backend
Run: uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import init_db
from backend.routers import categories, products, cart, orders, favourites
from backend.routers import admin, banners, public_settings, collections
from backend.routers import parser

log = logging.getLogger(__name__)
UPLOAD_DIR = Path("static/uploads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    await init_db()
    log.info("Backend started")
    yield
    log.info("Backend stopped")


app = FastAPI(
    title="TG-Shop API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(categories.router, prefix="/api/v1")
app.include_router(products.router,   prefix="/api/v1")
app.include_router(cart.router,       prefix="/api/v1")
app.include_router(orders.router,     prefix="/api/v1")
app.include_router(favourites.router, prefix="/api/v1")
app.include_router(banners.router,    prefix="/api/v1")
app.include_router(collections.router, prefix="/api/v1")
app.include_router(public_settings.router, prefix="/api/v1")
app.include_router(admin.router,      prefix="/api/v1")
app.include_router(parser.router,     prefix="/api/v1")

# Static files
app.mount("/static", StaticFiles(directory="static", html=False), name="static")


# Healthcheck (важно для Railway)
@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}
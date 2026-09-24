import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .routers import auth, ingest, leads, match
from .scheduler import background_loop
from .screener import background_loop as screener_loop

logging.basicConfig(level=logging.INFO)

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    tasks = [asyncio.create_task(background_loop()), asyncio.create_task(screener_loop())]
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title="Bureau", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(leads.router)
app.include_router(ingest.router)
app.include_router(match.router)

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

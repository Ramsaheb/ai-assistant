from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import router
from app.utils.logger import logger

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Monday.com BI Agent starting up")
    yield
    logger.info("Monday.com BI Agent shutting down")


app = FastAPI(
    title="Monday.com BI Agent",
    description="AI-powered business intelligence agent that connects to Monday.com boards "
                "and delivers founder-level insights with full chain-of-thought tracing.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    """Serve the conversational frontend UI."""
    return FileResponse(FRONTEND_DIR / "index.html")
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config_manager import get_settings
from core.engine import router as engine_router
from modules.video_analysis.router import router as video_router
from modules.video_analysis.async_router import router as video_async_router

app = FastAPI(title="Content Moderation Engine")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(engine_router)
app.include_router(video_router)
app.include_router(video_async_router)
# Add others as needed

@app.get("/")
def root():
    return {"message": "Content Moderation Engine Running"}

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}

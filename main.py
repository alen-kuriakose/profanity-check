import logging
from fastapi import FastAPI
from core.config_manager import get_settings
from core.engine import router as engine_router
from modules.video_analysis.router import router as video_router
# Import other routers as you add them

app = FastAPI(title="Content Moderation Engine")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Include routers
app.include_router(engine_router)
app.include_router(video_router)
# Add others as needed

@app.get("/")
def root():
    return {"message": "Content Moderation Engine Running"}

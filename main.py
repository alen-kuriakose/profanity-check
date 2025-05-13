import logging
import os
from logging.handlers import RotatingFileHandler
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config_manager import get_settings
from core.engine import router as engine_router
from modules.video_analysis.router import router as video_router
from modules.video_analysis.async_router import router as video_async_router

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Configure logging to file and console
log_file_path = os.path.join(logs_dir, 'app.log')

# Set up root logger - using a single configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # Console handler
        logging.StreamHandler(stream=sys.stdout),
        # File handler with rotation (10MB max size, keep 5 backup files)
        RotatingFileHandler(
            log_file_path, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
    ]
)

# Get the root logger for reference
root_logger = logging.getLogger()

# Get a logger for this module
logger = logging.getLogger(__name__)
logger.info(f"Logging to file: {log_file_path}")

# Test log messages at different levels
logger.debug("This is a debug message")
logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")

# Initialize FastAPI app
app = FastAPI(title="Content Moderation Engine")

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

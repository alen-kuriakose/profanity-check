"""
Script to run the video analysis worker service.
"""
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from modules.video_analysis.service import start_service

if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configure logging to file and console
    log_file_path = os.path.join(logs_dir, 'workers.log')
    
    # Set up root logger
    logging.basicConfig(
        level=logging.INFO,
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
    
    logger = logging.getLogger("run_workers")
    logger.info(f"Logging to file: {log_file_path}")
    logger.info("Starting video analysis worker service")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Python version: {sys.version}")
    
    # Start the service
    try:
        logger.info("Calling start_service()")
        start_service()
    except Exception as e:
        logger.exception(f"Error starting service: {str(e)}")
        sys.exit(1)
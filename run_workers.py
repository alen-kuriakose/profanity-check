"""
Script to run the video analysis worker service.
"""
import logging
import sys
import os
from modules.video_analysis.service import start_service

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout  # Ensure logs go to stdout
    )
    
    logger = logging.getLogger("run_workers")
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
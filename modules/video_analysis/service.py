"""
Service for running video analysis workers.
"""
import time
import logging
import threading
import signal
import sys
from typing import Dict, Any, List

from modules.video_analysis.kafka.consumer import (
    start_consumer,
    stop_all_consumers,
    TOPIC_VIDEO_UPLOADED,
    TOPIC_NSFW_ANALYSIS,
    TOPIC_VIOLENCE_ANALYSIS,
    TOPIC_PROFANITY_ANALYSIS,
    TOPIC_COMBINED_ANALYSIS,
    GROUP_ID_COORDINATOR,
    GROUP_ID_NSFW,
    GROUP_ID_VIOLENCE,
    GROUP_ID_PROFANITY,
    GROUP_ID_COMBINED
)
from modules.video_analysis.workers.coordinator import (
    process_video_upload,
    check_for_completed_analyses,
    check_for_pending_videos
)
from modules.video_analysis.workers.nsfw_worker import process_nsfw_analysis
from modules.video_analysis.workers.violence_worker import process_violence_analysis
from modules.video_analysis.workers.profanity_worker import process_profanity_analysis
from modules.video_analysis.workers.combined_worker import process_combined_analysis

logger = logging.getLogger(__name__)

# Flag to control the service
running = True

def handle_signal(signum, frame):
    """Handle termination signals."""
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False

def periodic_check():
    """Periodically check for completed analyses and pending videos."""
    global running
    
    logger.info("Starting periodic check thread")
    
    while running:
        try:
            # Check for completed analyses
            check_for_completed_analyses()
            
            # Check for pending videos
            check_for_pending_videos()
            
        except Exception as e:
            logger.exception(f"Error in periodic check: {str(e)}")
        
        # Sleep for a while
        for _ in range(60):  # Check every minute
            if not running:
                break
            time.sleep(1)
    
    logger.info("Periodic check thread stopped")

def start_service():
    """Start the video analysis service."""
    global running
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    logger.info("Starting video analysis service")
    
    try:
        # Start consumers
        logger.info(f"Starting consumer for topic {TOPIC_VIDEO_UPLOADED}")
        start_consumer(TOPIC_VIDEO_UPLOADED, GROUP_ID_COORDINATOR, process_video_upload)
        
        logger.info(f"Starting consumer for topic {TOPIC_NSFW_ANALYSIS}")
        start_consumer(TOPIC_NSFW_ANALYSIS, GROUP_ID_NSFW, process_nsfw_analysis)
        
        logger.info(f"Starting consumer for topic {TOPIC_VIOLENCE_ANALYSIS}")
        start_consumer(TOPIC_VIOLENCE_ANALYSIS, GROUP_ID_VIOLENCE, process_violence_analysis)
        
        logger.info(f"Starting consumer for topic {TOPIC_PROFANITY_ANALYSIS}")
        start_consumer(TOPIC_PROFANITY_ANALYSIS, GROUP_ID_PROFANITY, process_profanity_analysis)
        
        logger.info(f"Starting consumer for topic {TOPIC_COMBINED_ANALYSIS}")
        start_consumer(TOPIC_COMBINED_ANALYSIS, GROUP_ID_COMBINED, process_combined_analysis)
        
        # Start periodic check thread
        logger.info("Starting periodic check thread")
        check_thread = threading.Thread(target=periodic_check, daemon=True)
        check_thread.start()
        
        logger.info("Video analysis service started successfully")
        
        # Keep the main thread running
        counter = 0
        while running:
            time.sleep(1)
            counter += 1
            if counter % 60 == 0:  # Log every minute
                from modules.video_analysis.kafka.consumer import get_active_consumers
                active = get_active_consumers()
                logger.info(f"Service running. Active consumers: {active}")
            
    except Exception as e:
        logger.exception(f"Error in video analysis service: {str(e)}")
    finally:
        # Clean up
        logger.info("Stopping all consumers...")
        stop_all_consumers()
        logger.info("Video analysis service stopped")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start the service
    start_service()
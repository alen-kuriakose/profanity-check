"""
Service for running video analysis workers.

This service manages the Kafka consumers for video analysis, handling:
- Video upload processing
- NSFW content detection
- Violence detection
- Profanity detection
- Combined analysis results
"""
import time
import logging
import threading
import signal
import sys
import os
from typing import Dict, Any, List

from modules.video_analysis.kafka.consumer import (
    start_consumer,
    stop_all_consumers,
    TOPIC_VIDEO_UPLOADED,
    TOPIC_NSFW_ANALYSIS,
    TOPIC_VIOLENCE_ANALYSIS,
    TOPIC_PROFANITY_ANALYSIS,
    TOPIC_CLIP_ANALYSIS,
    TOPIC_COMBINED_ANALYSIS,
    GROUP_ID_COORDINATOR,
    GROUP_ID_NSFW,
    GROUP_ID_VIOLENCE,
    GROUP_ID_PROFANITY,
    GROUP_ID_CLIP,
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
from modules.video_analysis.workers.clip_worker import process_clip_analysis
from modules.video_analysis.workers.combined_worker import process_combined_analysis

# Configure enhanced logging
logger = logging.getLogger(__name__)

# Set up more detailed logging format if not already configured
if not logger.handlers:
    # Create logs directory if it doesn't exist
    try:
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Define log format with file name and line number for better debugging
        log_format = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        formatter = logging.Formatter(log_format)
        
        # Add file handler
        file_handler = logging.FileHandler(os.path.join(logs_dir, 'video_analysis_service.log'))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        logger.info("Enhanced logging configured for video analysis service")
    except Exception as e:
        logger.error(f"Error setting up logging: {e}")

# Flag to control the service
running = True

def handle_signal(signum, frame):
    """
    Handle termination signals (SIGINT, SIGTERM).
    
    This function is called when the service receives a termination signal,
    and it initiates a graceful shutdown by setting the running flag to False.
    
    Args:
        signum: Signal number received
        frame: Current stack frame
    """
    global running
    signal_names = {
        signal.SIGINT: "SIGINT",
        signal.SIGTERM: "SIGTERM"
    }
    signal_name = signal_names.get(signum, str(signum))
    
    logger.warning(f"Received termination signal {signal_name} ({signum}), initiating graceful shutdown...")
    running = False

def periodic_check():
    """
    Periodically check for completed analyses and pending videos.
    
    This function runs in a separate thread and performs two main tasks:
    1. Check for completed analyses that need to be processed
    2. Check for pending videos that need to be analyzed
    
    It runs every 60 seconds until the service is stopped.
    """
    global running
    
    logger.info("Starting periodic check thread for monitoring analysis status")
    check_count = 0
    
    while running:
        check_count += 1
        start_time = time.time()
        
        try:
            # Check for completed analyses
            logger.debug(f"Periodic check #{check_count}: Checking for completed analyses")
            completed = check_for_completed_analyses()
            if completed:
                logger.info(f"Periodic check #{check_count}: Found {len(completed)} completed analyses")
            
            # Check for pending videos
            logger.debug(f"Periodic check #{check_count}: Checking for pending videos")
            pending = check_for_pending_videos()
            if pending:
                logger.info(f"Periodic check #{check_count}: Found {len(pending)} pending videos")
            
            # Log performance metrics
            elapsed = time.time() - start_time
            if elapsed > 5:  # Log if check takes more than 5 seconds
                logger.warning(f"Periodic check #{check_count} took {elapsed:.2f} seconds to complete")
            else:
                logger.debug(f"Periodic check #{check_count} completed in {elapsed:.2f} seconds")
                
        except Exception as e:
            logger.exception(f"Error in periodic check #{check_count}: {str(e)}")
        
        # Sleep for a while, but check if we should stop every second
        for i in range(60):  # Check every minute
            if not running:
                logger.info("Periodic check detected shutdown signal, exiting loop")
                break
            time.sleep(1)
    
    logger.info(f"Periodic check thread stopped after {check_count} checks")

def start_service():
    """
    Start the video analysis service.
    
    This function:
    1. Sets up signal handlers for graceful shutdown
    2. Starts Kafka consumers for all analysis topics
    3. Starts the periodic check thread
    4. Maintains the main service loop
    5. Handles cleanup on shutdown
    
    The service will continue running until a termination signal is received
    or an unhandled exception occurs.
    """
    global running
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    logger.info("=== Starting video analysis service ===")
    start_time = time.time()
    
    try:
        # Start consumers for each analysis type
        logger.info(f"Starting consumer for video upload topic: {TOPIC_VIDEO_UPLOADED}")
        start_consumer(TOPIC_VIDEO_UPLOADED, GROUP_ID_COORDINATOR, process_video_upload)
        
        logger.info(f"Starting consumer for NSFW analysis topic: {TOPIC_NSFW_ANALYSIS}")
        start_consumer(TOPIC_NSFW_ANALYSIS, GROUP_ID_NSFW, process_nsfw_analysis)
        
        logger.info(f"Starting consumer for violence analysis topic: {TOPIC_VIOLENCE_ANALYSIS}")
        start_consumer(TOPIC_VIOLENCE_ANALYSIS, GROUP_ID_VIOLENCE, process_violence_analysis)
        
        logger.info(f"Starting consumer for profanity analysis topic: {TOPIC_PROFANITY_ANALYSIS}")
        start_consumer(TOPIC_PROFANITY_ANALYSIS, GROUP_ID_PROFANITY, process_profanity_analysis)
        
        logger.info(f"Starting consumer for CLIP analysis topic: {TOPIC_CLIP_ANALYSIS}")
        start_consumer(TOPIC_CLIP_ANALYSIS, GROUP_ID_CLIP, process_clip_analysis)
        
        logger.info(f"Starting consumer for combined analysis topic: {TOPIC_COMBINED_ANALYSIS}")
        start_consumer(TOPIC_COMBINED_ANALYSIS, GROUP_ID_COMBINED, process_combined_analysis)
        
        # Start periodic check thread for monitoring
        logger.info("Starting periodic check thread for monitoring analysis status")
        check_thread = threading.Thread(target=periodic_check, daemon=True, name="PeriodicCheckThread")
        check_thread.start()
        
        # Log successful startup
        startup_time = time.time() - start_time
        logger.info(f"=== Video analysis service started successfully in {startup_time:.2f} seconds ===")
        
        # Keep the main thread running and monitor service health
        counter = 0
        service_uptime = 0
        from modules.video_analysis.kafka.consumer import get_active_consumers, list_consumers
        
        while running:
            time.sleep(1)
            counter += 1
            service_uptime += 1
            
            # Log service status every minute
            if counter % 60 == 0:
                active_consumers = get_active_consumers()
                expected_consumers = 6  # We expect 6 consumers to be running (including CLIP)
                
                if len(active_consumers) < expected_consumers:
                    logger.warning(f"Service health check: Only {len(active_consumers)}/{expected_consumers} consumers active: {active_consumers}")
                    # Log detailed consumer status
                    consumer_status = list_consumers()
                    logger.info(f"Detailed consumer status: {consumer_status}")
                else:
                    logger.info(f"Service health check: All {len(active_consumers)} consumers active: {active_consumers}")
                
                # Log service uptime
                hours, remainder = divmod(service_uptime, 3600)
                minutes, seconds = divmod(remainder, 60)
                logger.info(f"Service uptime: {hours:02}:{minutes:02}:{seconds:02}")
            
    except Exception as e:
        logger.exception(f"Critical error in video analysis service: {str(e)}")
    finally:
        # Clean up resources on shutdown
        logger.warning("Initiating service shutdown sequence...")
        
        try:
            # Stop all Kafka consumers
            logger.info("Stopping all Kafka consumers...")
            stop_all_consumers()
            
            # Calculate service runtime
            runtime = time.time() - start_time
            hours, remainder = divmod(int(runtime), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            logger.info(f"=== Video analysis service stopped after running for {hours:02}:{minutes:02}:{seconds:02} ===")
        except Exception as cleanup_error:
            logger.error(f"Error during service shutdown: {str(cleanup_error)}")

if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        # Just send a SIGTERM to any running service
        import os
        import signal
        import subprocess
        
        try:
            # Try to find the PID of the running service
            result = subprocess.run(
                ["pgrep", "-f", "python.*modules.video_analysis.service"],
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                pid = int(result.stdout.strip())
                print(f"Sending SIGTERM to process {pid}")
                os.kill(pid, signal.SIGTERM)
                print("Signal sent. Service should stop shortly.")
            else:
                print("No running video analysis service found.")
            
            sys.exit(0)
        except Exception as e:
            print(f"Error stopping service: {e}")
            sys.exit(1)
    
    # Use centralized logging configuration
    try:
        from modules.logging_config import configure_module_logging
        
        # Configure module-specific log levels
        module_config = {
            'modules.video_analysis': logging.INFO,
            'modules.video_analysis.kafka': logging.INFO,
            'modules.video_analysis.workers': logging.INFO,
            'modules.video_analysis.database': logging.INFO,
            'modules.video_analysis.analysis': logging.INFO,
            'modules.video_analysis.service': logging.INFO,
            'kafka': logging.WARNING,  # Reduce Kafka noise
            'urllib3': logging.WARNING,  # Reduce HTTP client noise
        }
        
        # Apply configuration
        configure_module_logging(module_config)
        
        logger.info("Centralized logging configuration applied")
    except ImportError as e:
        print(f"Could not import logging_config module: {e}")
        # Fall back to basic logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    except Exception as e:
        print(f"Error setting up logging: {e}")
        # Fall back to basic logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Log system information
    import platform
    logger.info(f"Starting on {platform.node()} - Python {platform.python_version()} - {platform.system()} {platform.release()}")
    
    # Start the service
    start_service()
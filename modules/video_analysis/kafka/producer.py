"""
Kafka producer for video analysis.
"""
import json
import logging
import os
import importlib
from typing import Dict, Any

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
from modules.config import get_settings

logger = logging.getLogger(__name__)

# Get Kafka settings
settings = get_settings()
kafka_config = settings.kafka

# Initialize Kafka producer
_producer = None
_kafka_available = True

def get_kafka_producer():
    """Get or initialize the Kafka producer."""
    global _producer, _kafka_available
    if _producer is None and _kafka_available:
        try:
            _producer = KafkaProducer(
                bootstrap_servers=kafka_config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3,
                max_in_flight_requests_per_connection=1
            )
            logger.info(f"Kafka producer initialized with bootstrap servers: {kafka_config.bootstrap_servers}")
        except NoBrokersAvailable as e:
            logger.warning(f"No Kafka brokers available: {str(e)}. Using direct processing instead.")
            _kafka_available = False
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {str(e)}")
            _kafka_available = False
    return _producer

def send_message(topic: str, message: Dict[str, Any], key: str = None):
    """Send a message to a Kafka topic."""
    global _kafka_available
    
    # If Kafka is not available, process the message directly
    if not _kafka_available:
        logger.info(f"Kafka not available, processing message directly: {message}")
        
        # For video upload messages, process directly
        if topic == TOPIC_VIDEO_UPLOADED:
            try:
                # Import coordinator module dynamically to avoid circular imports
                coordinator_module = importlib.import_module('modules.video_analysis.workers.coordinator')
                # Set the direct processing flag
                coordinator_module.USE_DIRECT_PROCESSING = True
                # Process the video
                coordinator_module.process_video_upload(message)
                return True
            except Exception as e:
                logger.error(f"Failed to process message directly: {str(e)}")
                return False
        
        # For other messages, just log and return success
        logger.info(f"Message would be sent to topic {topic}: {message}")
        return True
    
    # If Kafka is available, send the message
    try:
        producer = get_kafka_producer()
        if producer is None:
            logger.warning("Kafka producer is None, processing message directly")
            if topic == TOPIC_VIDEO_UPLOADED:
                # Import coordinator module dynamically to avoid circular imports
                coordinator_module = importlib.import_module('modules.video_analysis.workers.coordinator')
                # Set the direct processing flag
                coordinator_module.USE_DIRECT_PROCESSING = True
                # Process the video
                coordinator_module.process_video_upload(message)
            return True
            
        future = producer.send(topic, value=message, key=key)
        # Wait for the message to be sent
        record_metadata = future.get(timeout=10)
        logger.info(f"Message sent to topic {topic} [{record_metadata.partition}] at offset {record_metadata.offset}")
        return True
    except NoBrokersAvailable:
        logger.warning("No Kafka brokers available, switching to direct processing")
        _kafka_available = False
        return send_message(topic, message, key)  # Retry with direct processing
    except Exception as e:
        logger.error(f"Failed to send message to topic {topic}: {str(e)}")
        return False

def close_producer():
    """Close the Kafka producer."""
    global _producer
    if _producer is not None:
        _producer.close()
        _producer = None
        logger.info("Kafka producer closed")

# Define topic names
TOPIC_VIDEO_UPLOADED = "video-analysis-uploaded"
TOPIC_NSFW_ANALYSIS = "video-analysis-nsfw"
TOPIC_VIOLENCE_ANALYSIS = "video-analysis-violence"
TOPIC_PROFANITY_ANALYSIS = "video-analysis-profanity"
TOPIC_COMBINED_ANALYSIS = "video-analysis-combined"

def send_video_uploaded_message(video_id: int, content_id: str, file_path: str):
    """Send a message indicating a video has been uploaded and is ready for processing."""
    logger.info(f"Preparing to send video uploaded message for content_id: {content_id}, video_id: {video_id}")
    message = {
        "video_id": video_id,
        "content_id": content_id,
        "file_path": file_path,
        "action": "process"
    }
    result = send_message(TOPIC_VIDEO_UPLOADED, message, key=content_id)
    logger.info(f"Video uploaded message for content_id: {content_id} sent: {result}")
    return result

def send_nsfw_analysis_request(video_id: int, content_id: str, file_path: str, analysis_id: int):
    """Send a request for NSFW analysis."""
    message = {
        "video_id": video_id,
        "content_id": content_id,
        "file_path": file_path,
        "analysis_id": analysis_id,
        "action": "analyze"
    }
    return send_message(TOPIC_NSFW_ANALYSIS, message, key=content_id)

def send_violence_analysis_request(video_id: int, content_id: str, file_path: str, analysis_id: int):
    """Send a request for violence analysis."""
    message = {
        "video_id": video_id,
        "content_id": content_id,
        "file_path": file_path,
        "analysis_id": analysis_id,
        "action": "analyze"
    }
    return send_message(TOPIC_VIOLENCE_ANALYSIS, message, key=content_id)

def send_profanity_analysis_request(video_id: int, content_id: str, file_path: str, analysis_id: int):
    """Send a request for profanity analysis."""
    message = {
        "video_id": video_id,
        "content_id": content_id,
        "file_path": file_path,
        "analysis_id": analysis_id,
        "action": "analyze"
    }
    return send_message(TOPIC_PROFANITY_ANALYSIS, message, key=content_id)

def send_combined_analysis_request(video_id: int, content_id: str, analysis_id: int):
    """Send a request for combined analysis."""
    message = {
        "video_id": video_id,
        "content_id": content_id,
        "analysis_id": analysis_id,
        "action": "combine"
    }
    return send_message(TOPIC_COMBINED_ANALYSIS, message, key=content_id)
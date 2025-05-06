"""
Kafka consumers for video analysis.
"""
import json
import logging
import threading
import time
from typing import Dict, Any, Callable, List

from kafka import KafkaConsumer
from modules.config import get_settings

logger = logging.getLogger(__name__)

# Get Kafka settings
settings = get_settings()
kafka_config = settings.kafka

# Consumer groups
GROUP_ID_COORDINATOR = "video-analysis-coordinator"
GROUP_ID_NSFW = "video-analysis-nsfw"
GROUP_ID_VIOLENCE = "video-analysis-violence"
GROUP_ID_PROFANITY = "video-analysis-profanity"
GROUP_ID_CLIP = "video-analysis-clip"
GROUP_ID_COMBINED = "video-analysis-combined"

# Topic names (same as in producer.py)
TOPIC_VIDEO_UPLOADED = "video-analysis-uploaded"
TOPIC_NSFW_ANALYSIS = "video-analysis-nsfw"
TOPIC_VIOLENCE_ANALYSIS = "video-analysis-violence"
TOPIC_PROFANITY_ANALYSIS = "video-analysis-profanity"
TOPIC_CLIP_ANALYSIS = "video-analysis-clip"
TOPIC_COMBINED_ANALYSIS = "video-analysis-combined"

# Active consumers
_consumers = {}
_consumer_threads = {}
_running = True

def create_consumer(topic: str, group_id: str):
    """Create a Kafka consumer for a specific topic and group."""
    try:
        logger.info(f"Creating Kafka consumer for topic {topic}, group {group_id}, bootstrap servers: {kafka_config.bootstrap_servers}")
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=kafka_config.bootstrap_servers,
            group_id=group_id,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            key_deserializer=lambda x: x.decode('utf-8') if x else None
        )
        logger.info(f"Successfully created Kafka consumer for topic {topic}, group {group_id}")
        return consumer
    except NoBrokersAvailable as e:
        logger.error(f"No Kafka brokers available at {kafka_config.bootstrap_servers}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to create Kafka consumer for topic {topic}, group {group_id}: {str(e)}")
        raise

def start_consumer(topic: str, group_id: str, message_handler: Callable[[Dict[str, Any]], None]):
    """Start a consumer in a separate thread."""
    global _consumers, _consumer_threads, _running
    
    # Create a unique key for this consumer
    consumer_key = f"{topic}_{group_id}"
    
    # Check if consumer already exists
    if consumer_key in _consumers:
        logger.warning(f"Consumer for topic {topic}, group {group_id} already exists")
        return
    
    # Create the consumer
    consumer = create_consumer(topic, group_id)
    _consumers[consumer_key] = consumer
    
    # Define the consumer thread function
    def consume_messages():
        logger.info(f"Starting to consume messages from topic {topic}, group {group_id}")
        try:
            for message in consumer:
                if not _running:
                    break
                
                try:
                    # Extract message data
                    key = message.key
                    value = message.value
                    partition = message.partition
                    offset = message.offset
                    
                    logger.debug(f"Received message from topic {topic} [{partition}] at offset {offset}: {value}")
                    
                    # Process the message
                    message_handler(value)
                    
                except Exception as e:
                    logger.error(f"Error processing message from topic {topic}: {str(e)}")
        except Exception as e:
            logger.error(f"Error in consumer thread for topic {topic}: {str(e)}")
        finally:
            logger.info(f"Consumer thread for topic {topic}, group {group_id} is shutting down")
            consumer.close()
    
    # Start the consumer thread
    thread = threading.Thread(target=consume_messages, daemon=True)
    thread.start()
    _consumer_threads[consumer_key] = thread
    
    logger.info(f"Started consumer thread for topic {topic}, group {group_id}")

def stop_all_consumers():
    """Stop all running consumers."""
    global _consumers, _consumer_threads, _running
    
    logger.info("Stopping all Kafka consumers")
    _running = False
    
    # Close all consumers
    for key, consumer in _consumers.items():
        try:
            consumer.close()
            logger.info(f"Closed consumer {key}")
        except Exception as e:
            logger.error(f"Error closing consumer {key}: {str(e)}")
    
    # Wait for all threads to finish
    for key, thread in _consumer_threads.items():
        try:
            thread.join(timeout=5)
            logger.info(f"Thread {key} joined")
        except Exception as e:
            logger.error(f"Error joining thread {key}: {str(e)}")
    
    # Clear the dictionaries
    _consumers.clear()
    _consumer_threads.clear()
    
    # Reset the running flag
    _running = True
    
    logger.info("All Kafka consumers stopped")

def is_consumer_running(topic: str, group_id: str) -> bool:
    """Check if a consumer is running."""
    consumer_key = f"{topic}_{group_id}"
    return consumer_key in _consumer_threads and _consumer_threads[consumer_key].is_alive()

def get_active_consumers() -> List[str]:
    """Get a list of active consumers."""
    return [key for key, thread in _consumer_threads.items() if thread.is_alive()]

def list_consumers():
    """List all consumers and their status."""
    result = {}
    for key, thread in _consumer_threads.items():
        result[key] = {
            "alive": thread.is_alive(),
            "daemon": thread.daemon,
            "name": thread.name
        }
    return result
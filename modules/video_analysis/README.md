# Video Analysis Pipeline

This module provides a comprehensive video analysis pipeline for detecting inappropriate content in videos. It includes:

- NSFW content detection
- Violence detection
- Profanity detection (in audio and text)
- Combined analysis

## Architecture

The pipeline uses a microservices architecture with the following components:

1. **FastAPI Web Service**: Handles HTTP requests and responses
2. **Kafka Message Broker**: Manages asynchronous processing
3. **PostgreSQL Database**: Stores video metadata and analysis results
4. **Worker Service**: Processes videos asynchronously

## Components

### Database

The database schema includes the following tables:

- `videos`: Stores metadata about uploaded videos
- `nsfw_analysis`: Stores NSFW analysis results
- `violence_analysis`: Stores violence analysis results
- `profanity_analysis`: Stores profanity analysis results
- `combined_analysis`: Stores combined analysis results

### Kafka Topics

The following Kafka topics are used:

- `video-analysis-uploaded`: Videos that have been uploaded and are ready for processing
- `video-analysis-nsfw`: NSFW analysis requests
- `video-analysis-violence`: Violence analysis requests
- `video-analysis-profanity`: Profanity analysis requests
- `video-analysis-combined`: Combined analysis requests

### Worker Service

The worker service consists of the following components:

- **Coordinator**: Manages the analysis process
- **NSFW Worker**: Detects NSFW content in videos
- **Violence Worker**: Detects violent content in videos
- **Profanity Worker**: Detects profanity in video audio and text
- **Combined Worker**: Combines the results of the individual analyses

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL
- Kafka
- Docker and Docker Compose (for development)

### Development Environment

1. Start the development environment:

```bash
docker-compose -f docker-compose.dev.yml up -d
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the API server:

```bash
uvicorn main:app --reload
```

4. Run the worker service:

```bash
python run_workers.py
```

### Environment Variables

The following environment variables can be set:

- `DB_HOST`: PostgreSQL host (default: localhost)
- `DB_PORT`: PostgreSQL port (default: 5432)
- `DB_NAME`: PostgreSQL database name (default: igot)
- `DB_USER`: PostgreSQL username (default: postgres)
- `DB_PASSWORD`: PostgreSQL password (default: postgres)
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers (default: localhost:9092)
- `VIDEO_STORAGE_PATH`: Path to store uploaded videos (default: /tmp/igot/videos)
- `ENABLE_VIDEO_ANALYSIS`: Enable/disable video analysis (default: true)

## API Endpoints

### Synchronous API

- `POST /video-analysis/nsfw-check`: Check a video for NSFW content
- `POST /video-analysis/violence-check`: Check a video for violent content
- `POST /video-analysis/profanity-check`: Check a video for profanity
- `POST /video-analysis/analyze`: Analyze a video for all types of inappropriate content

### Asynchronous API

- `POST /video-analysis-async/upload`: Upload a video for asynchronous analysis
- `GET /video-analysis-async/status/{content_id}`: Get the status of video analysis
- `GET /video-analysis-async/results/{content_id}`: Get the results of video analysis
- `POST /video-analysis-async/analyze/{content_id}`: Trigger analysis for a previously uploaded video
- `GET /video-analysis-async/health`: Check the health of the video analysis service

## Models

The pipeline uses the following models:

- **NSFW Detection**: Hugging Face's `Falconsai/nsfw_image_detection` model
- **Violence Detection**: Hugging Face's `Falconsai/nsfw_image_detection` model (repurposed)
- **Audio Transcription**: OpenAI's Whisper model
- **Text Detection**: PaddleOCR and Tesseract OCR
- **Profanity Detection**: Better Profanity library

## Flow

1. A video is uploaded via the API
2. The video is stored on disk and its metadata is saved in the database
3. A message is sent to Kafka to trigger analysis
4. The coordinator receives the message and initiates NSFW, violence, and profanity analyses
5. Each analysis is performed independently and in parallel
6. When all analyses are complete, a combined analysis is performed
7. The results are stored in the database and can be retrieved via the API

## Performance Considerations

- Videos are processed frame by frame, but not every frame is analyzed (typically every 30th frame)
- Frames are resized to a smaller dimension for faster processing
- The pipeline can be scaled horizontally by running multiple worker instances
- The database and Kafka can be scaled independently

## Error Handling

- If a video cannot be processed, its status is set to "failed" in the database
- If an individual analysis fails, it is marked as "failed" but other analyses continue
- The API provides detailed error messages when something goes wrong
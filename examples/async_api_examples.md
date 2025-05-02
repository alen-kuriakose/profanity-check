# Asynchronous Video Analysis API Examples

This document provides examples of how to use the asynchronous video analysis API using cURL.

## Prerequisites

- The API server is running
- The worker service is running
- PostgreSQL and Kafka are running

## Upload a Video

```bash
curl -X POST "http://localhost:8000/video-analysis-async/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "content_id=video123" \
  -F "file=@/path/to/your/video.mp4" \
  -F "analyze=true"
```

Response:

```json
{
  "content_id": "video123",
  "filename": "video.mp4",
  "file_size": 1234567,
  "status": "queued",
  "message": "Video uploaded successfully"
}
```

## Check Analysis Status

```bash
curl -X GET "http://localhost:8000/video-analysis-async/status/video123" \
  -H "accept: application/json"
```

Response:

```json
{
  "content_id": "video123",
  "filename": "video.mp4",
  "upload_timestamp": "2023-06-01T12:34:56.789Z",
  "video_status": "processing",
  "processing_started_at": "2023-06-01T12:35:00.000Z",
  "processing_completed_at": null,
  "analysis_status": {
    "nsfw": "completed",
    "violence": "processing",
    "profanity": "completed",
    "combined": "pending"
  },
  "content_rating": null
}
```

## Get Analysis Results

```bash
curl -X GET "http://localhost:8000/video-analysis-async/results/video123" \
  -H "accept: application/json"
```

Response:

```json
{
  "content_id": "video123",
  "filename": "video.mp4",
  "status": "completed",
  "content_rating": "explicit",
  "summary": {
    "inappropriate_frames": 15,
    "total_frames_analyzed": 120,
    "inappropriate_percentage": 12.5
  }
}
```

## Get Detailed Analysis Results

```bash
curl -X GET "http://localhost:8000/video-analysis-async/results/video123?include_details=true" \
  -H "accept: application/json"
```

Response:

```json
{
  "content_id": "video123",
  "filename": "video.mp4",
  "status": "completed",
  "content_rating": "explicit",
  "summary": {
    "inappropriate_frames": 15,
    "total_frames_analyzed": 120,
    "inappropriate_percentage": 12.5
  },
  "details": {
    "nsfw": {
      "frames_analyzed": 120,
      "nsfw_frames": 10,
      "nsfw_percentage": 8.33,
      "max_nsfw_confidence": 0.95,
      "processing_time_seconds": 15.2,
      "frames_per_second": 7.89,
      "frame_results": [
        {
          "frame_number": 30,
          "timestamp_seconds": 1.0,
          "timestamp_formatted": "00:00:01",
          "is_nsfw": true,
          "nsfw_confidence": 0.95,
          "all_categories": {
            "nsfw": 0.95,
            "neutral": 0.05
          }
        }
      ]
    },
    "violence": {
      "frames_analyzed": 120,
      "violent_frames": 5,
      "violence_percentage": 4.17,
      "max_violence_confidence": 0.85,
      "processing_time_seconds": 12.5,
      "frames_per_second": 9.6,
      "frame_results": [
        {
          "frame_number": 60,
          "timestamp_seconds": 2.0,
          "timestamp_formatted": "00:00:02",
          "is_violent": true,
          "violence_confidence": 0.85,
          "all_categories": {
            "violent": 0.85,
            "non_violent": 0.15
          }
        }
      ]
    },
    "profanity": {
      "has_profanity": true,
      "method": "audio_transcription",
      "transcript": "This is a sample transcript with some profanity...",
      "profanity_confidence": 0.75,
      "processing_time_seconds": 8.3
    },
    "combined": {
      "content_rating": "explicit",
      "inappropriate_frames": 15,
      "total_frames_analyzed": 120,
      "inappropriate_percentage": 12.5,
      "nsfw_analysis": {
        "frames": 10,
        "percentage": 8.33,
        "max_confidence": 0.95
      },
      "violence_analysis": {
        "frames": 5,
        "percentage": 4.17,
        "max_confidence": 0.85
      },
      "profanity_analysis": {
        "frames": 0,
        "has_profanity": true,
        "method": "audio_transcription",
        "max_confidence": 0.75
      }
    }
  }
}
```

## Trigger Analysis for a Previously Uploaded Video

```bash
curl -X POST "http://localhost:8000/video-analysis-async/analyze/video123" \
  -H "accept: application/json"
```

Response:

```json
{
  "content_id": "video123",
  "status": "queued",
  "message": "Analysis triggered successfully"
}
```

## Check API Health

```bash
curl -X GET "http://localhost:8000/video-analysis-async/health" \
  -H "accept: application/json"
```

Response:

```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "kafka": "healthy"
  }
}
```
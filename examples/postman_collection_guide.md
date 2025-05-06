# Video Analysis API - Postman Collection Guide

This guide explains how to import and use the Postman collection for testing the Video Analysis API.

## Importing the Collection

1. Open Postman
2. Click on "Import" in the top left corner
3. Select the `video_analysis_postman_collection.json` file
4. Click "Import"

## Setting Up Environment Variables

The collection uses a variable `{{baseUrl}}` which is set to `http://localhost:8000` by default. If your API is running on a different host or port, you can create an environment to override this:

1. Click on "Environments" in the sidebar
2. Click "Create Environment"
3. Name it (e.g., "Video Analysis Local")
4. Add a variable:
   - Variable: `baseUrl`
   - Initial Value: `http://localhost:8000` (or your custom URL)
   - Current Value: `http://localhost:8000` (or your custom URL)
5. Click "Save"
6. Select your environment from the dropdown in the top right corner

## Using the Collection

The collection is organized into three folders:

### 1. General

Basic endpoints to check if the API is running:
- **Root Endpoint**: `GET /`
- **Health Check**: `GET /health`

### 2. Synchronous Analysis

Endpoints that process videos immediately and return results:
- **NSFW Check**: `POST /video-analysis/nsfw-check`
- **Violence Check**: `POST /video-analysis/violence-check`
- **Profanity Check**: `POST /video-analysis/profanity-check`
- **Comprehensive Analysis**: `POST /video-analysis/analyze`

For these endpoints, you need to:
1. Select a video file using the "Select Files" button in the form-data section
2. Adjust parameters as needed (frame_interval, confidence_threshold, etc.)
3. Click "Send"

### 3. Asynchronous Analysis

Endpoints that queue videos for processing and allow checking status and results later:
- **Upload Video**: `POST /video-analysis-async/upload`
- **Check Analysis Status**: `GET /video-analysis-async/status/{content_id}`
- **Get Analysis Results**: `GET /video-analysis-async/results/{content_id}`
- **Get Detailed Analysis Results**: `GET /video-analysis-async/results/{content_id}?include_details=true`
- **Trigger Analysis**: `POST /video-analysis-async/analyze/{content_id}`
- **Check API Health**: `GET /video-analysis-async/health`

For the asynchronous workflow:
1. First upload a video using the "Upload Video" endpoint
2. Note the `content_id` from the response
3. Check the status using the "Check Analysis Status" endpoint
4. Once the status shows as completed, get the results using the "Get Analysis Results" endpoint

## Important Notes

1. **File Paths**: You need to update the file paths in the requests to point to your actual video files.

2. **Content IDs**: The collection uses `video123` as a placeholder for content IDs. Replace this with your actual content IDs when testing.

3. **Worker Service**: For the asynchronous endpoints to work properly, make sure the worker service is running:
   ```bash
   cd /path/to/igot
   python run_workers.py
   ```

4. **Kafka**: The asynchronous pipeline requires Kafka to be running. If you're not using Kafka, only the synchronous endpoints will work properly.

## Example Workflow

1. Test if the API is running using the "Root Endpoint" request
2. Upload a video using the "Upload Video" request (update the file path first)
3. Check the status using the "Check Analysis Status" request
4. Once completed, get the results using the "Get Analysis Results" request
5. For more detailed results, use the "Get Detailed Analysis Results" request
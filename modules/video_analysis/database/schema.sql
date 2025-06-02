-- Video Analysis Database Schema

-- Videos table to store uploaded videos
CREATE TABLE IF NOT EXISTS videos (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(255) NOT NULL UNIQUE,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    upload_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE
);

-- Create index on content_id and status for faster lookups
CREATE INDEX IF NOT EXISTS idx_videos_content_id ON videos(content_id);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);

-- NSFW analysis results
CREATE TABLE IF NOT EXISTS nsfw_analysis (
    id SERIAL PRIMARY KEY,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    frames_analyzed INTEGER,
    nsfw_frames INTEGER,
    nsfw_percentage FLOAT,
    max_nsfw_confidence FLOAT,
    processing_time_seconds FLOAT,
    frames_per_second FLOAT,
    result_data JSONB,
    error_message TEXT
);

-- Violence analysis results
CREATE TABLE IF NOT EXISTS violence_analysis (
    id SERIAL PRIMARY KEY,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    frames_analyzed INTEGER,
    violent_frames INTEGER,
    violence_percentage FLOAT,
    max_violence_confidence FLOAT,
    processing_time_seconds FLOAT,
    frames_per_second FLOAT,
    result_data JSONB,
    error_message TEXT
);

-- Profanity analysis results
CREATE TABLE IF NOT EXISTS profanity_analysis (
    id SERIAL PRIMARY KEY,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    method VARCHAR(50) CHECK (method IN ('audio_transcription', 'ocr_text_detection', NULL)),
    has_profanity BOOLEAN,
    profanity_frames INTEGER,
    frames_analyzed INTEGER,
    max_profanity_confidence FLOAT,
    processing_time_seconds FLOAT,
    transcript TEXT,
    all_segments JSONB,
    segments_with_profanity JSONB,
    full_transcript_available BOOLEAN DEFAULT FALSE,
    result_data JSONB,
    error_message TEXT
);

-- Combined analysis results (aggregated from individual analyses)
CREATE TABLE IF NOT EXISTS combined_analysis (
    id SERIAL PRIMARY KEY,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    completed_at TIMESTAMP WITH TIME ZONE,
    content_rating VARCHAR(50) CHECK (content_rating IN ('safe', 'questionable', 'explicit', 'violent', 'profane', NULL)),
    inappropriate_frames INTEGER,
    total_frames_analyzed INTEGER,
    inappropriate_percentage FLOAT,
    result_data JSONB
);

-- Create a view to easily check the status of all analyses for a video
CREATE OR REPLACE VIEW video_analysis_status AS
SELECT 
    v.id AS video_id,
    v.content_id,
    v.filename,
    v.status AS video_status,
    n.status AS nsfw_status,
    vio.status AS violence_status,
    p.status AS profanity_status,
    c.status AS combined_status,
    c.content_rating,
    v.upload_timestamp,
    v.processing_started_at,
    v.processing_completed_at
FROM 
    videos v
LEFT JOIN nsfw_analysis n ON v.id = n.video_id
LEFT JOIN violence_analysis vio ON v.id = vio.video_id
LEFT JOIN profanity_analysis p ON v.id = p.video_id
LEFT JOIN combined_analysis c ON v.id = c.video_id;
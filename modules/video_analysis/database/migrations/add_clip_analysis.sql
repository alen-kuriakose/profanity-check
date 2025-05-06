-- Migration to add CLIP analysis table

-- CLIP analysis results
CREATE TABLE IF NOT EXISTS clip_analysis (
    id SERIAL PRIMARY KEY,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    method VARCHAR(50) DEFAULT 'clip',
    has_problematic_content BOOLEAN DEFAULT FALSE,
    categories_detected TEXT,
    frames_with_issues INTEGER,
    frames_analyzed INTEGER,
    processing_time_seconds FLOAT,
    result_data JSONB,
    error_message TEXT
);

-- Create index on video_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_clip_analysis_video_id ON clip_analysis(video_id);
CREATE INDEX IF NOT EXISTS idx_clip_analysis_status ON clip_analysis(status);

-- Update the video_analysis_status view to include CLIP analysis
DROP VIEW IF EXISTS video_analysis_status;
CREATE VIEW video_analysis_status AS
SELECT 
    v.id AS video_id,
    v.content_id,
    v.filename,
    v.status AS video_status,
    n.status AS nsfw_status,
    vio.status AS violence_status,
    p.status AS profanity_status,
    clip.status AS clip_status,
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
LEFT JOIN clip_analysis clip ON v.id = clip.video_id
LEFT JOIN combined_analysis c ON v.id = c.video_id;
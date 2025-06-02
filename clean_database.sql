-- SQL script to clean all records from the database while keeping schema and tables intact
-- This uses TRUNCATE which is faster than DELETE and resets sequences

-- Disable foreign key constraints temporarily to avoid truncation issues
SET session_replication_role = 'replica';

-- Truncate all tables
TRUNCATE TABLE combined_analysis CASCADE;
TRUNCATE TABLE nsfw_analysis CASCADE;
TRUNCATE TABLE profanity_analysis CASCADE;
TRUNCATE TABLE videos CASCADE;
TRUNCATE TABLE violence_analysis CASCADE;

-- Re-enable foreign key constraints
SET session_replication_role = 'origin';

-- Confirm tables are empty
SELECT 'combined_analysis' as table_name, COUNT(*) as row_count FROM combined_analysis
UNION ALL
SELECT 'nsfw_analysis' as table_name, COUNT(*) as row_count FROM nsfw_analysis
UNION ALL
SELECT 'profanity_analysis' as table_name, COUNT(*) as row_count FROM profanity_analysis
UNION ALL
SELECT 'videos' as table_name, COUNT(*) as row_count FROM videos
UNION ALL
SELECT 'violence_analysis' as table_name, COUNT(*) as row_count FROM violence_analysis;
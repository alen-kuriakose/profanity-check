"""
Database connection and operations for video analysis.
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import ThreadedConnectionPool

from modules.config import get_settings

logger = logging.getLogger(__name__)

# Initialize connection pool
settings = get_settings()
db_config = settings.database

# Create a connection pool
pool = None

def init_db_pool():
    """Initialize the database connection pool."""
    global pool
    try:
        pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=db_config.host,
            port=db_config.port,
            dbname=db_config.name,
            user=db_config.user,
            password=db_config.password
        )
        logger.info("Database connection pool initialized")
        
        # Initialize schema if needed
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Read schema file
                schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
                with open(schema_path, "r") as f:
                    schema_sql = f.read()
                
                # Execute schema
                cur.execute(schema_sql)
                conn.commit()
                logger.info("Database schema initialized")
                
    except Exception as e:
        logger.error(f"Failed to initialize database connection pool: {str(e)}")
        raise

def get_db_connection():
    """Get a connection from the pool."""
    if pool is None:
        init_db_pool()
    return pool.getconn()

def release_db_connection(conn):
    """Release a connection back to the pool."""
    if pool is not None:
        pool.putconn(conn)

class DBContextManager:
    """Context manager for database connections."""
    
    def __enter__(self):
        self.conn = get_db_connection()
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        release_db_connection(self.conn)

# Video operations
def insert_video(content_id: str, filename: str, file_path: str, file_size: int, mime_type: str) -> int:
    """Insert a new video record and return its ID."""
    with DBContextManager() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO videos (content_id, filename, file_path, file_size, mime_type)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (content_id, filename, file_path, file_size, mime_type)
            )
            result = cur.fetchone()
            conn.commit()
            return result['id']

def get_video_by_content_id(content_id: str) -> Optional[Dict[str, Any]]:
    """Get a video by content ID."""
    with DBContextManager() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM videos
                WHERE content_id = %s
                """,
                (content_id,)
            )
            return cur.fetchone()

def update_video_status(video_id: int, status: str) -> bool:
    """Update the status of a video."""
    with DBContextManager() as conn:
        with conn.cursor() as cur:
            if status == 'processing':
                cur.execute(
                    """
                    UPDATE videos
                    SET status = %s, processing_started_at = NOW()
                    WHERE id = %s
                    """,
                    (status, video_id)
                )
            elif status == 'completed' or status == 'failed':
                cur.execute(
                    """
                    UPDATE videos
                    SET status = %s, processing_completed_at = NOW()
                    WHERE id = %s
                    """,
                    (status, video_id)
                )
            else:
                cur.execute(
                    """
                    UPDATE videos
                    SET status = %s
                    WHERE id = %s
                    """,
                    (status, video_id)
                )
            conn.commit()
            return cur.rowcount > 0

def get_pending_videos(limit: int = 10) -> List[Dict[str, Any]]:
    """Get videos with pending status."""
    with DBContextManager() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM videos
                WHERE status = 'pending'
                ORDER BY upload_timestamp ASC
                LIMIT %s
                """,
                (limit,)
            )
            return cur.fetchall()

# NSFW analysis operations
def insert_nsfw_analysis(video_id: int) -> int:
    """Insert a new NSFW analysis record and return its ID."""
    with DBContextManager() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO nsfw_analysis (video_id)
                VALUES (%s)
                RETURNING id
                """,
                (video_id,)
            )
            result = cur.fetchone()
            conn.commit()
            return result['id']

def update_nsfw_analysis(analysis_id: int, status: str, **kwargs) -> bool:
    """Update an NSFW analysis record."""
    with DBContextManager() as conn:
        with conn.cursor() as cur:
            # Build the SQL query dynamically based on the provided kwargs
            sql = "UPDATE nsfw_analysis SET status = %s"
            params = [status]
            
            if status == 'processing':
                sql += ", started_at = NOW()"
            elif status == 'completed':
                sql += ", completed_at = NOW()"
            
            # Add additional fields from kwargs
            for key, value in kwargs.items():
                if key == 'result_data':
                    sql += f", {key} = %s::jsonb"
                else:
                    sql += f", {key} = %s"
                params.append(value)
            
            # Add the WHERE clause
            sql += " WHERE id = %s"
            params.append(analysis_id)
            
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount > 0

# Violence analysis operations
def insert_violence_analysis(video_id: int) -> int:
    """Insert a new violence analysis record and return its ID."""
    with DBContextManager() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO violence_analysis (video_id)
                VALUES (%s)
                RETURNING id
                """,
                (video_id,)
            )
            result = cur.fetchone()
            conn.commit()
            return result['id']

def update_violence_analysis(analysis_id: int, status: str, **kwargs) -> bool:
    """Update a violence analysis record."""
    with DBContextManager() as conn:
        with conn.cursor() as cur:
            # Build the SQL query dynamically based on the provided kwargs
            sql = "UPDATE violence_analysis SET status = %s"
            params = [status]
            
            if status == 'processing':
                sql += ", started_at = NOW()"
            elif status == 'completed':
                sql += ", completed_at = NOW()"
            
            # Add additional fields from kwargs
            for key, value in kwargs.items():
                if key == 'result_data':
                    sql += f", {key} = %s::jsonb"
                else:
                    sql += f", {key} = %s"
                params.append(value)
            
            # Add the WHERE clause
            sql += " WHERE id = %s"
            params.append(analysis_id)
            
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount > 0

# Profanity analysis operations
def insert_profanity_analysis(video_id: int) -> int:
    """Insert a new profanity analysis record and return its ID."""
    with DBContextManager() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO profanity_analysis (video_id)
                VALUES (%s)
                RETURNING id
                """,
                (video_id,)
            )
            result = cur.fetchone()
            conn.commit()
            return result['id']

def update_profanity_analysis(analysis_id: int, status: str, **kwargs) -> bool:
    """Update a profanity analysis record."""
    with DBContextManager() as conn:
        with conn.cursor() as cur:
            # Build the SQL query dynamically based on the provided kwargs
            sql = "UPDATE profanity_analysis SET status = %s"
            params = [status]
            
            if status == 'processing':
                sql += ", started_at = NOW()"
            elif status == 'completed':
                sql += ", completed_at = NOW()"
            
            # Add additional fields from kwargs
            for key, value in kwargs.items():
                if key == 'result_data':
                    sql += f", {key} = %s::jsonb"
                else:
                    sql += f", {key} = %s"
                params.append(value)
            
            # Add the WHERE clause
            sql += " WHERE id = %s"
            params.append(analysis_id)
            
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount > 0

# Combined analysis operations
def insert_combined_analysis(video_id: int) -> int:
    """Insert a new combined analysis record and return its ID."""
    with DBContextManager() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO combined_analysis (video_id)
                VALUES (%s)
                RETURNING id
                """,
                (video_id,)
            )
            result = cur.fetchone()
            conn.commit()
            return result['id']

def update_combined_analysis(analysis_id: int, status: str, **kwargs) -> bool:
    """Update a combined analysis record."""
    with DBContextManager() as conn:
        with conn.cursor() as cur:
            # Build the SQL query dynamically based on the provided kwargs
            sql = "UPDATE combined_analysis SET status = %s"
            params = [status]
            
            if status == 'completed':
                sql += ", completed_at = NOW()"
            
            # Add additional fields from kwargs
            for key, value in kwargs.items():
                if key == 'result_data':
                    sql += f", {key} = %s::jsonb"
                else:
                    sql += f", {key} = %s"
                params.append(value)
            
            # Add the WHERE clause
            sql += " WHERE id = %s"
            params.append(analysis_id)
            
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount > 0

# Analysis status and results
def get_analysis_status(video_id: int) -> Dict[str, Any]:
    """Get the status of all analyses for a video."""
    with DBContextManager() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM video_analysis_status
                WHERE video_id = %s
                """,
                (video_id,)
            )
            return cur.fetchone() or {}

def get_analysis_results(video_id: int) -> Dict[str, Any]:
    """Get the results of all analyses for a video."""
    with DBContextManager() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get NSFW analysis
            cur.execute(
                """
                SELECT * FROM nsfw_analysis
                WHERE video_id = %s
                """,
                (video_id,)
            )
            nsfw_analysis = cur.fetchone()
            
            # Get violence analysis
            cur.execute(
                """
                SELECT * FROM violence_analysis
                WHERE video_id = %s
                """,
                (video_id,)
            )
            violence_analysis = cur.fetchone()
            
            # Get profanity analysis
            cur.execute(
                """
                SELECT * FROM profanity_analysis
                WHERE video_id = %s
                """,
                (video_id,)
            )
            profanity_analysis = cur.fetchone()
            
            # Get combined analysis
            cur.execute(
                """
                SELECT * FROM combined_analysis
                WHERE video_id = %s
                """,
                (video_id,)
            )
            combined_analysis = cur.fetchone()
            
            return {
                "nsfw_analysis": nsfw_analysis,
                "violence_analysis": violence_analysis,
                "profanity_analysis": profanity_analysis,
                "combined_analysis": combined_analysis
            }

def get_videos_with_completed_analyses() -> List[Dict[str, Any]]:
    """Get videos where all individual analyses are completed but combined analysis is pending."""
    with DBContextManager() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT v.id, v.content_id
                FROM videos v
                JOIN nsfw_analysis n ON v.id = n.video_id
                JOIN violence_analysis vio ON v.id = vio.video_id
                JOIN profanity_analysis p ON v.id = p.video_id
                LEFT JOIN combined_analysis c ON v.id = c.video_id
                WHERE n.status = 'completed'
                AND vio.status = 'completed'
                AND p.status = 'completed'
                AND (c.status IS NULL OR c.status = 'pending')
                """
            )
            return cur.fetchall()

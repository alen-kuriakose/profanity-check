"""
Video storage module for handling video files.
"""
import os
import uuid
import shutil
import logging
from typing import Tuple
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from modules.config import get_settings

logger = logging.getLogger(__name__)

# Get storage settings
settings = get_settings()
storage_config = settings.storage

def get_storage_path() -> str:
    """Get the base storage path for videos."""
    base_path = storage_config.video_storage_path
    
    # Create the directory if it doesn't exist
    os.makedirs(base_path, exist_ok=True)
    
    return base_path

def generate_storage_path(content_id: str) -> Tuple[str, str]:
    """
    Generate a storage path for a video file.
    
    Returns:
        Tuple[str, str]: (directory_path, file_path)
    """
    # Create a directory structure based on date to avoid too many files in one directory
    today = datetime.now().strftime("%Y/%m/%d")
    
    # Create a unique filename
    unique_id = str(uuid.uuid4())
    
    # Combine to create the directory path
    base_path = get_storage_path()
    dir_path = os.path.join(base_path, today, content_id)
    
    # Create the directory
    os.makedirs(dir_path, exist_ok=True)
    
    # Return both the directory path and the full file path
    return dir_path, os.path.join(dir_path, unique_id)

def save_uploaded_video(content_id: str, file: UploadFile) -> Tuple[str, int]:
    """
    Save an uploaded video file to storage.
    
    Args:
        content_id: The content ID for the video
        file: The uploaded file
        
    Returns:
        Tuple[str, int]: (file_path, file_size)
    """
    # Generate storage path
    dir_path, file_path_without_ext = generate_storage_path(content_id)
    
    # Get file extension from the uploaded file
    _, ext = os.path.splitext(file.filename)
    if not ext:
        ext = ".mp4"  # Default extension if none is provided
    
    # Complete file path with extension
    file_path = f"{file_path_without_ext}{ext}"
    
    # Save the file
    try:
        # Reset file position
        file.file.seek(0)
        
        # Write the file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        logger.info(f"Saved video file for content ID {content_id} to {file_path} ({file_size} bytes)")
        
        return file_path, file_size
    except Exception as e:
        logger.error(f"Failed to save video file for content ID {content_id}: {str(e)}")
        # Clean up if file was partially written
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

def delete_video_file(file_path: str) -> bool:
    """
    Delete a video file.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        bool: True if the file was deleted, False otherwise
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted video file: {file_path}")
            
            # Try to remove the parent directory if it's empty
            parent_dir = os.path.dirname(file_path)
            if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
                logger.info(f"Removed empty directory: {parent_dir}")
                
            return True
        else:
            logger.warning(f"Video file not found for deletion: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Failed to delete video file {file_path}: {str(e)}")
        return False

def get_video_file_info(file_path: str) -> dict:
    """
    Get information about a video file.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        dict: File information
    """
    try:
        if not os.path.exists(file_path):
            logger.warning(f"Video file not found: {file_path}")
            return {}
        
        file_stat = os.stat(file_path)
        file_info = {
            "path": file_path,
            "size": file_stat.st_size,
            "created": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
            "exists": True
        }
        
        return file_info
    except Exception as e:
        logger.error(f"Failed to get video file info for {file_path}: {str(e)}")
        return {"path": file_path, "exists": False, "error": str(e)}
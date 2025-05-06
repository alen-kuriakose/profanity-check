"""
Centralized logging configuration for the iGOT application.

This module provides a consistent logging setup across all components of the application.
It configures:
- Console logging for development
- File logging for production
- Proper formatting with timestamps, module names, and line numbers
- Different log levels for different components
"""
import os
import logging
import logging.handlers
import sys
from typing import Optional, Dict, Any

# Default log format with detailed information for debugging
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'

# Simplified format for console output
CONSOLE_LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

def setup_logging(
    module_name: str,
    log_level: int = logging.INFO,
    log_file: Optional[str] = None,
    console: bool = True,
    log_format: str = DEFAULT_LOG_FORMAT,
    console_format: str = CONSOLE_LOG_FORMAT,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up logging for a module.
    
    Args:
        module_name: Name of the module (used for the logger name)
        log_level: Logging level (default: INFO)
        log_file: Path to log file (if None, will use module_name.log in logs directory)
        console: Whether to log to console (default: True)
        log_format: Format string for log messages
        console_format: Format string for console messages
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(module_name)
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatters
    file_formatter = logging.Formatter(log_format)
    console_formatter = logging.Formatter(console_format)
    
    # Add file handler if log_file is specified or can be created
    if log_file is None:
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, f"{module_name.replace('.', '_')}.log")
    
    try:
        # Create directory for log file if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        
        # Use rotating file handler to prevent logs from growing too large
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except (IOError, PermissionError) as e:
        sys.stderr.write(f"Warning: Could not set up log file {log_file}: {e}\n")
    
    # Add console handler if requested
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger

def configure_module_logging(module_config: Dict[str, Any] = None) -> None:
    """
    Configure logging for all modules based on configuration.
    
    Args:
        module_config: Dictionary mapping module names to log levels
    """
    # Default configuration for modules
    default_config = {
        'modules.video_analysis': logging.INFO,
        'modules.video_analysis.kafka': logging.INFO,
        'modules.video_analysis.workers': logging.INFO,
        'modules.video_analysis.database': logging.INFO,
        'modules.video_analysis.analysis': logging.INFO,
        'kafka': logging.WARNING,  # Reduce Kafka noise
        'urllib3': logging.WARNING,  # Reduce HTTP client noise
        'PIL': logging.WARNING,  # Reduce PIL noise
    }
    
    # Update with provided configuration
    if module_config:
        default_config.update(module_config)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)  # Set default level for all other modules
    
    # Configure each module
    for module, level in default_config.items():
        setup_logging(module, log_level=level)
    
    # Log configuration complete
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured for {len(default_config)} modules")

# Example usage:
# if __name__ == "__main__":
#     configure_module_logging()
#     logger = logging.getLogger(__name__)
#     logger.info("Logging test")
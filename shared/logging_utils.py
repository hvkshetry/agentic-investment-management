"""
Logging utilities for proper configuration without side effects.
"""
import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(name: str, level: int = logging.INFO, log_file: Optional[Path] = None) -> logging.Logger:
    """
    Set up a logger with proper configuration.
    
    This function should only be called from main entry points, 
    not from library modules.
    
    Args:
        name: Logger name (usually __name__ from the calling module)
        level: Logging level (default: INFO)
        log_file: Optional path to log file
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_library_logger(name: str) -> logging.Logger:
    """
    Get a logger for library modules that doesn't affect global configuration.
    
    Library modules should use this instead of logging.basicConfig().
    
    Args:
        name: Logger name (usually __name__ from the calling module)
        
    Returns:
        Logger with NullHandler to avoid side effects
    """
    logger = logging.getLogger(name)
    
    # Add NullHandler to prevent unwanted output in library mode
    # This can be overridden by the application using the library
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    
    return logger


def setup_mcp_server_logging(server_name: str, log_dir: Optional[Path] = None) -> logging.Logger:
    """
    Standard logging setup for MCP servers.
    
    Args:
        server_name: Name of the MCP server
        log_dir: Optional directory for log files (default: ./logs)
        
    Returns:
        Configured logger for the server
    """
    if log_dir is None:
        log_dir = Path("./logs")
    
    log_file = log_dir / f"{server_name}.log"
    
    # Configure root logger for the server
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Get server-specific logger
    logger = setup_logger(server_name, logging.INFO, log_file)
    
    # Set third-party library log levels to reduce noise
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('yfinance').setLevel(logging.WARNING)
    logging.getLogger('openbb').setLevel(logging.WARNING)
    
    return logger
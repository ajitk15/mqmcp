import logging
import json
import datetime
import os
import sys

class JSONFormatter(logging.Formatter):
    """
    100% JSON Formatter for all project logs to allow easy stat generation.
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add any extra metrics/context if passed via 'extra' dictionary
        if hasattr(record, "metrics"):
            log_record["metrics"] = record.metrics
        if hasattr(record, "context"):
            log_record["context"] = record.context

        # If there's an exception, include full traceback inline
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record)

def setup_json_logger(name: str, log_file_env_var: str, default_log_path: str) -> logging.Logger:
    """
    Sets up a logger that outputs 100% JSON text lines to a specified file and stderr.
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if logger is imported multiple times
    if logger.handlers:
        return logger
        
    logger.setLevel(os.getenv("MQ_LOG_LEVEL", "INFO").upper())
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)

    # Determine log file path based on Environment Variable or Fallback
    log_file = os.getenv(log_file_env_var, default_log_path)
    
    # Make path absolute relative to project root (since this script is in `utils/`)
    if not os.path.isabs(log_file):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        log_file = os.path.join(project_root, log_file)
        
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        
    # Setup file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    # Do not propagate up to root logger to avoid standard terminal logs printing twice
    logger.propagate = False
    
    return logger

def get_api_logger():
    return setup_json_logger("api_client", "MQ_API_LOG_FILE", "logs/API.log")

def get_app_logger():
    return setup_json_logger("application", "MQ_APP_LOG_FILE", "logs/APP.log")

def get_mcp_logger():
    return setup_json_logger("mcp_server", "MQ_MCP_LOG_FILE", "logs/mcpserver.log")

import logging
import json
import time
import datetime
import sys
import os

class SplunkMetricsFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings compatible with Splunk.
    Includes automatic timestamping and metadata.
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "app": "mqmcp-ecosystem"
        }
        
        # Add metrics if present in extra
        if hasattr(record, "metrics"):
            log_record["metrics"] = record.metrics
            
        # Add context if present
        if hasattr(record, "context"):
            log_record["context"] = record.context
            
        return json.dumps(log_record)

def get_metrics_logger(name="mqmcp-metrics"):
    """
    Configure and return a logger specifically for Splunk metrics.
    Logs to stderr by default to avoid protocol interference.
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Stream to stderr
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(SplunkMetricsFormatter())
        logger.addHandler(handler)
        
        # Optionally log to a file if MQ_LOG_FILE is set
        log_file = os.getenv("MQ_LOG_FILE")
        if log_file:
            # Ensure directory exists
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(SplunkMetricsFormatter())
            logger.addHandler(file_handler)
            
    return logger

class MetricsTracker:
    """
    A context manager to track execution time and log metrics.
    """
    def __init__(self, logger, tool_name, context=None):
        self.logger = logger
        self.tool_name = tool_name
        self.context = context or {}
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        status = "success" if exc_type is None else "error"
        
        metrics = {
            "tool": self.tool_name,
            "execution_time_ms": round(duration_ms, 2),
            "status": status
        }
        
        if exc_type:
            metrics["error_type"] = exc_type.__name__
            metrics["error_msg"] = str(exc_val)
            self.logger.error(f"Execution of {self.tool_name} failed", 
                            extra={"metrics": metrics, "context": self.context})
        else:
            self.logger.info(f"Execution of {self.tool_name} completed", 
                           extra={"metrics": metrics, "context": self.context})

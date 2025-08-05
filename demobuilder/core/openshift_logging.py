"""
OpenShift Native Logging for DemoBuilder

This module provides structured logging that integrates seamlessly with OpenShift's
container-native logging infrastructure. All logs are sent to stdout/stderr in JSON
format for automatic collection by OpenShift logging stack.
"""

import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from functools import wraps
import streamlit as st


class OpenShiftLogger:
    """
    OpenShift-native logger that outputs structured JSON logs to stdout.
    Automatically enriches logs with OpenShift context (pod, namespace, node).
    """
    
    def __init__(self, component: str = "demobuilder"):
        self.component = component
        self.session_id = self._get_or_create_session_id()
        self.logger = self._setup_logger()
        
        # OpenShift environment context
        self.openshift_context = {
            "pod_name": os.getenv('POD_NAME', 'unknown'),
            "pod_namespace": os.getenv('POD_NAMESPACE', 'default'),
            "node_name": os.getenv('NODE_NAME', 'unknown'),
            "cluster_name": os.getenv('CLUSTER_NAME', 'unknown'),
            "deployment": os.getenv('DEPLOYMENT_NAME', component)
        }
        
    def _get_or_create_session_id(self) -> str:
        """Get or create session ID for Streamlit session tracking"""
        if 'logging_session_id' not in st.session_state:
            st.session_state.logging_session_id = str(uuid.uuid4())
        return st.session_state.logging_session_id
    
    def _setup_logger(self) -> logging.Logger:
        """Setup JSON logger that outputs to stdout for OpenShift collection"""
        logger = logging.getLogger(f"demobuilder.{self.component}")
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Create stdout handler for OpenShift logging
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        
        # JSON formatter for structured logging
        formatter = OpenShiftJSONFormatter()
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        logger.propagate = False
        
        return logger
    
    def _get_base_log_data(self) -> Dict[str, Any]:
        """Get base log data with OpenShift context"""
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "component": self.component,
            "session_id": self.session_id,
            "openshift": self.openshift_context.copy(),
            "app": "demobuilder",
            "version": os.getenv('APP_VERSION', 'unknown')
        }
    
    def log_event(self, event_type: str, level: str = "INFO", **kwargs):
        """Log a structured event with OpenShift context"""
        log_data = self._get_base_log_data()
        log_data.update({
            "event_type": event_type,
            "event_data": kwargs
        })
        
        # Log at appropriate level
        if level.upper() == "ERROR":
            self.logger.error(json.dumps(log_data))
        elif level.upper() == "WARNING":
            self.logger.warning(json.dumps(log_data))
        elif level.upper() == "DEBUG":
            self.logger.debug(json.dumps(log_data))
        else:
            self.logger.info(json.dumps(log_data))
    
    def log_user_action(self, action: str, user_id: str = None, **kwargs):
        """Log user interaction events"""
        user_info = self._get_user_context()
        
        self.log_event(
            "user_action",
            action=action,
            user_id=user_id or user_info.get('user_id', 'anonymous'),
            user_roles=user_info.get('roles', []),
            authenticated=user_info.get('authenticated', False),
            **kwargs
        )
    
    def log_infrastructure_request(self, providers: List[str], instance_count: int, **kwargs):
        """Log infrastructure configuration requests"""
        self.log_event(
            "infrastructure_request",
            providers=providers,
            instance_count=instance_count,
            provider_count=len(providers),
            **kwargs
        )
    
    def log_yaml_generation(self, success: bool, providers: List[str], error: str = None, **kwargs):
        """Log YAML generation attempts"""
        self.log_event(
            "yaml_generation",
            level="ERROR" if not success else "INFO",
            success=success,
            providers=providers,
            error=error,
            **kwargs
        )
    
    def log_performance_metric(self, operation: str, duration_ms: float, **kwargs):
        """Log performance metrics"""
        self.log_event(
            "performance_metric",
            operation=operation,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_error(self, error_type: str, error_message: str, **kwargs):
        """Log application errors"""
        self.log_event(
            "application_error",
            level="ERROR",
            error_type=error_type,
            error_message=error_message,
            **kwargs
        )
    
    def _get_user_context(self) -> Dict[str, Any]:
        """Extract user context from Streamlit session"""
        user_info = st.session_state.get('user_info', {})
        return {
            'user_id': user_info.get('user', 'anonymous'),
            'roles': user_info.get('roles', []),
            'authenticated': user_info.get('authenticated', False),
            'display_name': user_info.get('display_name', 'Anonymous User')
        }


class OpenShiftJSONFormatter(logging.Formatter):
    """Custom JSON formatter for OpenShift logging compatibility"""
    
    def format(self, record):
        # If the message is already JSON, return it as-is
        try:
            json.loads(record.getMessage())
            return record.getMessage()
        except (json.JSONDecodeError, ValueError):
            # Create structured log entry for non-JSON messages
            log_entry = {
                "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
            
            # Add exception info if present
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            
            return json.dumps(log_entry)


class DemoBuilderMetrics:
    """
    Metrics collection specifically for DemoBuilder user interactions
    """
    
    def __init__(self):
        self.logger = OpenShiftLogger("metrics")
        self.start_time = time.time()
    
    def track_session_start(self, user_agent: str = None):
        """Track user session initiation"""
        user_context = self.logger._get_user_context()
        
        self.logger.log_event(
            "session_start",
            user_id=user_context['user_id'],
            authenticated=user_context['authenticated'],
            user_agent=user_agent,
            start_time=datetime.utcnow().isoformat()
        )
    
    def track_provider_selection(self, enabled_providers: List[str], disabled_providers: List[str]):
        """Track provider selection patterns"""
        self.logger.log_event(
            "provider_selection",
            enabled_providers=enabled_providers,
            disabled_providers=disabled_providers,
            total_providers=len(enabled_providers) + len(disabled_providers)
        )
    
    def track_conversation_turn(self, turn_number: int, user_input_length: int, ai_response_length: int):
        """Track conversation interactions"""
        self.logger.log_event(
            "conversation_turn",
            turn_number=turn_number,
            user_input_length=user_input_length,
            ai_response_length=ai_response_length
        )
    
    def track_workflow_stage(self, stage: str, duration_seconds: float = None):
        """Track workflow progression"""
        self.logger.log_event(
            "workflow_stage",
            stage=stage,
            duration_seconds=duration_seconds
        )
    
    def track_yaml_download(self, config_size_bytes: int, providers: List[str]):
        """Track YAML configuration downloads"""
        self.logger.log_event(
            "yaml_download",
            config_size_bytes=config_size_bytes,
            providers=providers,
            provider_count=len(providers)
        )
    
    def track_error_recovery(self, error_type: str, recovery_action: str, success: bool):
        """Track error handling and recovery"""
        self.logger.log_event(
            "error_recovery",
            error_type=error_type,
            recovery_action=recovery_action,
            recovery_success=success
        )


def log_execution_time(operation_name: str):
    """Decorator to log execution time of functions"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = OpenShiftLogger("performance")
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.log_performance_metric(
                    operation=operation_name,
                    duration_ms=duration_ms,
                    success=True
                )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.log_performance_metric(
                    operation=operation_name,
                    duration_ms=duration_ms,
                    success=False,
                    error=str(e)
                )
                
                raise
        
        return wrapper
    return decorator


# Global logger instances
app_logger = OpenShiftLogger("app")
metrics = DemoBuilderMetrics()
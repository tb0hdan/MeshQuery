"""
Error handling utilities for the Malla application.
"""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import jsonify, request

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Custom API error class."""

    def __init__(self, message: str, status_code: int = 500, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)


def handle_api_errors(f: Callable) -> Callable:
    """Decorator to handle API errors consistently."""

    @wraps(f)
    def decorated_function(*args, **kwargs) -> Any:
        try:
            return f(*args, **kwargs)
        except APIError as e:
            logger.warning(f"API error in {f.__name__}: {e.message}")
            return jsonify(
                {
                    "error": e.message,
                    "error_code": e.error_code,
                    "status_code": e.status_code,
                }
            ), e.status_code
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {e}", exc_info=True)
            return jsonify(
                {
                    "error": "Internal server error",
                    "error_code": "INTERNAL_ERROR",
                    "status_code": 500,
                }
            ), 500

    return decorated_function


def validate_request_data(schema_class):
    """Decorator to validate request data using Marshmallow schemas."""

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Get request data
                if request.is_json:
                    data = request.get_json()
                else:
                    data = request.form.to_dict()

                # Validate data
                schema = schema_class()
                validated_data = schema.load(data)

                # Add validated data to kwargs
                kwargs["validated_data"] = validated_data

                return f(*args, **kwargs)

            except Exception as e:
                logger.warning(f"Validation error in {f.__name__}: {e}")
                return jsonify(
                    {
                        "error": "Invalid request data",
                        "error_code": "VALIDATION_ERROR",
                        "details": str(e),
                    }
                ), 400

        return decorated_function

    return decorator


def log_api_request(f: Callable) -> Callable:
    """Decorator to log API requests."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        logger.info(
            f"API request: {request.method} {request.path} from {request.remote_addr}"
        )
        return f(*args, **kwargs)

    return decorated_function


def rate_limit(max_requests: int = 100, window_seconds: int = 3600):
    """Simple rate limiting decorator."""

    # In-memory rate limiting (for production, use Redis)
    request_counts = {}

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            current_time = int(time.time())
            window_start = current_time - window_seconds

            # Clean old entries
            request_counts[client_ip] = [
                req_time
                for req_time in request_counts.get(client_ip, [])
                if req_time > window_start
            ]

            # Check rate limit
            if len(request_counts[client_ip]) >= max_requests:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return jsonify(
                    {
                        "error": "Rate limit exceeded",
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "retry_after": window_seconds,
                    }
                ), 429

            # Record this request
            request_counts[client_ip].append(current_time)

            return f(*args, **kwargs)

        return decorated_function

    return decorator

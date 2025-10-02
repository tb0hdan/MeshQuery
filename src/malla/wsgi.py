#!/usr/bin/env python3
"""
WSGI entry point for Malla Web UI with Gunicorn support.

This module provides the WSGI application factory and a main function
that starts Gunicorn with appropriate configuration for production deployment.
"""

import logging
import sys
from typing import Optional, Any, Iterable

from flask import Flask

from .config import get_config
from .web_ui import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def create_wsgi_app() -> Flask:
    """Create and return the WSGI application."""
    logger.info("Creating WSGI application for Gunicorn")
    return create_app()


# Lazy application creation to avoid config caching issues during testing
_application = None


def get_application() -> Flask:
    """Get the WSGI application instance, creating it if necessary."""
    global _application
    if _application is None:
        _application = create_wsgi_app()
    return _application


# WSGI application callable for servers - use a callable that defers execution
def application(environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
    """WSGI application entry point."""
    return get_application()(environ, start_response)


def main() -> None:
    """Main entry point for running with Gunicorn."""
    logger.info("Starting Malla Web UI with Gunicorn")

    try:
        # Import gunicorn here to avoid hard dependency when not using WSGI
        from gunicorn.app.wsgiapp import WSGIApplication

        # Get configuration
        cfg = get_config()

        # Configure Gunicorn with improved settings
        import multiprocessing

        # Calculate optimal worker count (CPU cores * 2 + 1, but cap at 8)
        worker_count = min(multiprocessing.cpu_count() * 2 + 1, 8)

        # Print startup information
        print("=" * 60)
        print("Malla Web UI (Gunicorn)")
        print("=" * 60)
        print(f"Database: {cfg.database_file}")
        print(f"Web UI: http://{cfg.host}:{cfg.port}")
        print(f"Workers: {worker_count}")
        print(f"Debug mode: {cfg.debug}")
        print("=" * 60)
        print()
        
        gunicorn_config = {
            "bind": f"{cfg.host}:{cfg.port}",
            "workers": worker_count,
            "worker_class": "gevent",  # Use gevent for better async handling
            "worker_connections": 1000,
            "max_requests": 1000,
            "max_requests_jitter": 50,
            "timeout": 30,
            "keepalive": 2,
            "preload_app": True,
            "access_log_format": '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s',
            "accesslog": "-",  # Log to stdout
            "errorlog": "-",  # Log to stderr
            "loglevel": "info",
            "capture_output": True,
            "enable_stdio_inheritance": True,
            # Add graceful timeout for better shutdown
            "graceful_timeout": 30,
            # Enable worker recycling to prevent memory leaks
            "max_worker_memory": 200,  # MB
        }

        # Create Gunicorn application
        class MallaWSGIApplication(WSGIApplication):
            def __init__(self, app: Flask, options: Optional[dict[str, Any]] = None) -> None:
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self) -> None:
                if hasattr(self, "cfg") and self.cfg:
                    config = {
                        key: value
                        for key, value in self.options.items()
                        if key in self.cfg.settings and value is not None
                    }
                    for key, value in config.items():
                        self.cfg.set(key.lower(), value)

            def load(self) -> Flask:
                return self.application

        # Start Gunicorn
        logger.info("Starting Gunicorn server on %s:%s", cfg.host, cfg.port)
        MallaWSGIApplication(get_application(), gunicorn_config).run()

    except ImportError:
        logger.error(
            "Gunicorn is not installed. Please install it with: pip install gunicorn"
        )
        sys.exit(1)
    except Exception as e:
        logger.error("Failed to start Gunicorn application: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

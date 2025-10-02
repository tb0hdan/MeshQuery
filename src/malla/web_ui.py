from __future__ import annotations

import os
from typing import Any, Optional

from flask import Flask
from markupsafe import Markup

from .config import get_config
from .routes.api_routes import api_bp
from .routes.gateway_routes import gateway_bp
from .routes.live_routes import live_bp
from .routes.main_routes import main_bp
from .routes.node_routes import node_bp
from .routes.packet_routes import packet_bp
from .routes.stream_routes import stream_bp
from .routes.traceroute_routes import traceroute_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # Set timezone globally
    config = get_config()
    os.environ["TZ"] = config.timezone

    # Register template filters
    @app.template_filter("format_rssi")
    def format_rssi(value: Optional[float]) -> str:
        """Format RSSI value for display."""
        if value is None:
            return "?"
        return f"{value:.0f}"

    @app.template_filter("format_snr")
    def format_snr(value: Optional[float]) -> str:
        """Format SNR value for display."""
        if value is None:
            return "?"
        return f"{value:.1f}"

    @app.template_filter("markdown")
    def markdown_filter(text: Optional[str]) -> str:
        """Convert markdown to HTML."""
        if not text:
            return ""
        try:
            import markdown

            return markdown.markdown(text)
        except ImportError:
            return text

    @app.template_filter("pretty_json")
    def pretty_json_filter(data: Any) -> Markup:
        """Convert data to pretty JSON string."""
        import json

        try:
            rendered = json.dumps(data, indent=2, default=str)
        except (TypeError, ValueError):
            rendered = str(data)
        return Markup(rendered)

    @app.template_filter("safe_json")
    def safe_json_filter(data: Any, indent: Optional[int] = None, **kwargs: Any) -> str:
        """Convert data to JSON string with optional indentation."""
        import json

        indent = kwargs.get("indent", indent)
        try:
            if indent is not None:
                rendered = json.dumps(data, indent=indent, default=str)
            else:
                rendered = json.dumps(data, default=str)
        except (TypeError, ValueError) as e:
            error_payload = {"error": f"JSON serialization error: {e}"}
            error_indent = indent if indent is not None else 2
            rendered = json.dumps(error_payload, indent=error_indent, default=str)
        return Markup(rendered)

    # Register all blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(stream_bp)
    app.register_blueprint(live_bp)
    app.register_blueprint(node_bp)
    app.register_blueprint(packet_bp)
    app.register_blueprint(gateway_bp)
    app.register_blueprint(traceroute_bp)

    # Initialize Tier B write-optimized pipeline
    try:
        from .services.tier_b_initializer import initialize_tier_b_pipeline

        if initialize_tier_b_pipeline():
            app.logger.info("Tier B write-optimized pipeline initialized successfully")
        else:
            app.logger.warning(
                "Tier B pipeline initialization failed - continuing with legacy pipeline"
            )
    except Exception as e:
        app.logger.warning(
            f"Failed to initialize Tier B pipeline: {e} - continuing with legacy pipeline"
        )

    return app


application = create_app()


def main() -> None:
    """Main entry point for running the Flask development server."""
    app = create_app()
    config = get_config()

    print("=" * 60)
    print("Malla Web UI (Flask Development Server)")
    print("=" * 60)
    print(f"Database: {config.database_file}")
    print(f"Web UI: http://{config.host}:{config.port}")
    print(f"Debug mode: {config.debug}")
    print("=" * 60)
    print()

    app.run(host=config.host, port=config.port, debug=config.debug)


if __name__ == "__main__":
    main()

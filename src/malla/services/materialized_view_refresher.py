"""
Background service for refreshing materialized views in the Tier B pipeline.

This service runs in the background to keep materialized views up to date,
ensuring fast query performance for the longest links analysis.
"""

import logging
import threading
import time

from ..database.schema_tier_b import refresh_longest_links_mv

logger = logging.getLogger(__name__)


class MaterializedViewRefresher:
    """
    Background service for refreshing materialized views.

    This service runs in a separate thread and periodically refreshes
    the longest_links_mv materialized view to keep it up to date.
    """

    def __init__(self, refresh_interval_minutes: int = 5):
        """
        Initialize the materialized view refresher.

        Args:
            refresh_interval_minutes: How often to refresh the materialized view (default: 5 minutes)
        """
        self.refresh_interval_minutes = refresh_interval_minutes
        self.refresh_interval_seconds = refresh_interval_minutes * 60
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the background refresh service."""
        if self._running:
            logger.warning("Materialized view refresher is already running")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._thread.start()

        logger.info(
            f"Started materialized view refresher (interval: {self.refresh_interval_minutes} minutes)"
        )

    def stop(self) -> None:
        """Stop the background refresh service."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

        logger.info("Stopped materialized view refresher")

    def _refresh_loop(self) -> None:
        """Main refresh loop that runs in the background thread."""
        logger.info("Materialized view refresher loop started")

        while self._running and not self._stop_event.is_set():
            try:
                # Refresh the materialized view
                refresh_longest_links_mv()

                # Wait for the next refresh interval
                if self._stop_event.wait(self.refresh_interval_seconds):
                    break  # Stop event was set

            except Exception as e:
                logger.error("Error refreshing materialized view: %s", e)
                # Continue running even if one refresh fails
                time.sleep(60)  # Wait a minute before retrying

        logger.info("Materialized view refresher loop stopped")

    def force_refresh(self) -> None:
        """Force an immediate refresh of the materialized view."""
        try:
            refresh_longest_links_mv()
            logger.info("Forced refresh of materialized view completed")
        except Exception as e:
            logger.error("Error in forced refresh: %s", e)

    def is_running(self) -> bool:
        """Check if the refresher is currently running."""
        return self._running and self._thread is not None and self._thread.is_alive()


# Global instance for the application
_refresher: MaterializedViewRefresher | None = None


def start_materialized_view_refresher(refresh_interval_minutes: int = 5) -> None:
    """
    Start the global materialized view refresher.

    Args:
        refresh_interval_minutes: How often to refresh (default: 5 minutes)
    """
    global _refresher

    if _refresher is not None:
        logger.warning("Materialized view refresher is already initialized")
        return

    _refresher = MaterializedViewRefresher(refresh_interval_minutes)
    _refresher.start()


def stop_materialized_view_refresher() -> None:
    """Stop the global materialized view refresher."""
    global _refresher

    if _refresher is not None:
        _refresher.stop()
        _refresher = None


def force_refresh_materialized_view() -> None:
    """Force an immediate refresh of the materialized view."""
    global _refresher

    if _refresher is not None:
        _refresher.force_refresh()
    else:
        # If no refresher is running, do a one-time refresh
        try:
            refresh_longest_links_mv()
            logger.info("One-time refresh of materialized view completed")
        except Exception as e:
            logger.error("Error in one-time refresh: %s", e)


def is_refresher_running() -> bool:
    """Check if the materialized view refresher is running."""
    global _refresher
    return _refresher is not None and _refresher.is_running()

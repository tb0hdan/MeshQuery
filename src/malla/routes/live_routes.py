
from flask import Blueprint, render_template

# Live routes blueprint.  In addition to the classic list‑style live packet
# feed (`/live`), this blueprint also serves a topographic live view.  The
# topographic page overlays nodes onto a Leaflet map with a topographic
# basemap and animates packets as they arrive via Server‑Sent Events.
live_bp = Blueprint("live", __name__)


@live_bp.route("/live")
def live_page() -> str:
    """List‑style live packet feed (legacy)."""
    return render_template("live_view.html")


@live_bp.route("/live-topography")
def live_topography_page() -> str:
    """Serve the topographic live map page."""
    return render_template("live_topography.html")


from flask import Blueprint, render_template
live_bp = Blueprint("live", __name__)
@live_bp.route("/live")
def live_page():
    return render_template("live_view.html")

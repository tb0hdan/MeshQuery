
from __future__ import annotations
import time, logging
from typing import Iterator
from flask import Blueprint, Response, stream_with_context
from ..database.connection_postgres import get_postgres_connection

logger = logging.getLogger(__name__)
stream_bp = Blueprint("stream", __name__, url_prefix="/stream")

@stream_bp.route("/packets")
def stream_packets() -> Response:
    def event_stream() -> Iterator[str]:
        conn = None
        try:
            conn = get_postgres_connection()
            conn.set_isolation_level(0)
            cur = conn.cursor()
            cur.execute("LISTEN packets;")
            logger.info("SSE listening on 'packets'")
            yield "event: ping\n"
            yield "data: {\"ok\":true}\n\n"
            while True:
                conn.poll()
                while conn.notifies:
                    n = conn.notifies.pop(0)
                    yield f"data: {n.payload}\n\n"
                time.sleep(0.25)
        except Exception as e:
            logger.warning("SSE error: %s", e)
        finally:
            try:
                if conn: conn.close()
            except Exception:
                pass
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(event_stream()), headers=headers)

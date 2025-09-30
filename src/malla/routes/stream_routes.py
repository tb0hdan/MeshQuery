
from __future__ import annotations
import time, logging, json
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
                    # Fetch the latest packet data
                    try:
                        cur.execute("""
                            SELECT timestamp, from_node_id, to_node_id, portnum, portnum_name,
                                   rssi, snr, hop_start, hop_limit, gateway_id, mesh_packet_id
                            FROM packet_history
                            ORDER BY timestamp DESC
                            LIMIT 1
                        """)
                        packet = cur.fetchone()
                        if packet:
                            # Calculate hop_count from hop_start and hop_limit
                            hop_count = None
                            # packet tuple indexes:
                            # 0: timestamp
                            # 1: from_node_id
                            # 2: to_node_id
                            # 3: portnum
                            # 4: portnum_name
                            # 5: rssi
                            # 6: snr
                            # 7: hop_start
                            # 8: hop_limit
                            # 9: gateway_id
                            # 10: mesh_packet_id
                            if packet[7] is not None and packet[8] is not None:
                                hop_count = packet[7] - packet[8]  # hop_start - hop_limit

                            # Create a packet dict with both shorthand and explicit names. The
                            # network graph and map pages expect keys `from_node_id` and
                            # `to_node_id`, while older code may still reference `from`/`to`.
                            packet_data = {
                                "ts": packet[0],
                                # Use both `from` and `from_node_id` for compatibility
                                "from": packet[1],
                                "from_node_id": packet[1],
                                "to": packet[2],
                                "to_node_id": packet[2],
                                "portnum": packet[3],
                                "portnum_name": packet[4],
                                "rssi": packet[5],
                                "snr": packet[6],
                                "hop_count": hop_count,
                                # Properly map gateway_id and mesh_packet_id based on select order
                                "gateway_id": packet[9],
                                "mesh_packet_id": packet[10],
                            }
                            yield f"data: {json.dumps(packet_data)}\n\n"
                        else:
                            yield f"data: {n.payload}\n\n"
                    except Exception as e:
                        logger.warning("Error fetching packet data: %s", e)
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


from __future__ import annotations
import threading
import logging
from typing import Any, Iterable
from .connection_postgres import get_postgres_connection, get_postgres_cursor

logger = logging.getLogger(__name__)

class DatabaseAdapter:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._connection = None
        self._cursor = None
        self._closed = True

    def get_connection(self):
        return get_postgres_connection()

    def get_cursor(self):
        return get_postgres_cursor(self._connection)

    def ensure_open(self) -> None:
        if self._connection is None or self._closed:
            self._connection = self.get_connection()
            self._cursor = self.get_cursor()
            self._closed = False

    def execute(self, query: str, params: tuple | None = None) -> None:
        with self._lock:
            self.ensure_open()
            try:
                self._cursor.execute(query, params or ())
                self._connection.commit()
            except Exception as e:
                self._connection.rollback()
                raise e

    def executemany(self, query: str, seq_of_params: Iterable[Iterable[Any]]) -> None:
        with self._lock:
            self.ensure_open()
            try:
                self._cursor.executemany(query, seq_of_params)
                self._connection.commit()
            except Exception as e:
                self._connection.rollback()
                raise e

    def fetchall(self, query: str | None = None, params: tuple | None = None):
        with self._lock:
            self.ensure_open()
            if query is not None:
                self._cursor.execute(query, params or ())
            return self._cursor.fetchall()

    def fetchone(self, query: str | None = None, params: tuple | None = None):
        with self._lock:
            self.ensure_open()
            if query is not None:
                self._cursor.execute(query, params or ())
            return self._cursor.fetchone()

    def get_placeholder(self) -> str:
        """Get the placeholder for parameterized queries."""
        return "%s"

    def close(self) -> None:
        with self._lock:
            try:
                if self._cursor:
                    self._cursor.close()
            except Exception:
                pass
            try:
                if self._connection:
                    self._connection.close()
            except Exception:
                pass
            self._closed = True

    def notify(self, channel: str, payload: str) -> None:
        with self._lock:
            try:
                self.ensure_open()
                self._cursor.execute(f"NOTIFY {channel}, %s;", (payload,))
                self._connection.commit()
            except Exception as e:
                logger.warning("NOTIFY failed: %s", e)

_singleton: DatabaseAdapter | None = None

def get_db_adapter() -> DatabaseAdapter:
    global _singleton
    if _singleton is None:
        _singleton = DatabaseAdapter()
    return _singleton

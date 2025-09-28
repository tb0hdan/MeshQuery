import os, sys, time
from pathlib import Path

DB_HOST = os.getenv("MALLA_DATABASE_HOST", "localhost")
DB_PORT = int(os.getenv("MALLA_DATABASE_PORT", "5432"))
DB_NAME = os.getenv("MALLA_DATABASE_NAME", "malla")
DB_USER = os.getenv("MALLA_DATABASE_USER", "malla")
DB_PASS = os.getenv("MALLA_DATABASE_PASSWORD", "yourpassword")
SCHEMA_SQL = os.getenv("MALLA_SCHEMA_SQL", "schema.sql")  # optional

def _connect(max_wait=60):
    import psycopg2
    start = time.time()
    last_err = None
    while time.time() - start < max_wait:
        try:
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                user=DB_USER, password=DB_PASS
            )
            conn.autocommit = True
            return conn
        except Exception as e:
            last_err = e
            time.sleep(1.5)
    raise RuntimeError(f"Could not connect to Postgres at {DB_HOST}:{DB_PORT}/{DB_NAME}: {last_err}")

def _run_schema_sql(conn):
    paths = []
    # explicit path via env (file or dir)
    if SCHEMA_SQL and SCHEMA_SQL.strip():
        p = Path(SCHEMA_SQL)
        if p.exists():
            if p.is_dir():
                # run *.sql in sorted order
                paths.extend(sorted(Path(SCHEMA_SQL).glob("*.sql")))
            else:
                paths.append(p)
    # common fallbacks
    for candidate in [
        Path("/app/src/malla/schema.sql"),
        Path("/app/src/malla/sql/schema.sql"),
        Path("/app/sql/schema.sql"),
    ]:
        if candidate.exists() and candidate not in paths:
            paths.append(candidate)
    if not paths:
        print("[db-init] No schema.sql found; skipping raw SQL step.")
        return
    with conn.cursor() as cur:
        for p in paths:
            sql = p.read_text(encoding="utf-8")
            print(f"[db-init] Applying SQL: {p}")
            cur.execute(sql)

def _try_call_python_schema(conn):
    # If project provides a pythonized schema initializer, call it.
    # We try a few conventional module names.
    module_names = [
        "malla.schema",
        "malla.schema_tier_b",
        "malla.db.schema",
    ]
    for name in module_names:
        try:
            mod = __import__(name, fromlist=["*"])
            for fn_name in ("ensure_schema", "init_schema", "create_all"):
                fn = getattr(mod, fn_name, None)
                if callable(fn):
                    print(f"[db-init] Calling {name}.{fn_name}()")
                    fn(conn)
                    return True
        except ModuleNotFoundError:
            continue
        except Exception as e:
            print(f"[db-init] {name} init failed: {e}", file=sys.stderr)
    print("[db-init] No python schema initializer found; skipped.")
    return False

def main():
    print("[db-init] Starting DB init")
    try:
        conn = _connect()
    except Exception as e:
        print(f"[db-init] Connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    ok_py = _try_call_python_schema(conn)
    if not ok_py:
        try:
            _run_schema_sql(conn)
        except Exception as e:
            print(f"[db-init] SQL schema step failed: {e}", file=sys.stderr)
            sys.exit(2)
    print("[db-init] Done")

if __name__ == "__main__":
    main()

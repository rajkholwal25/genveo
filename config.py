import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _sqlite_uri() -> str:
    return f"sqlite:///{os.path.join(BASE_DIR, 'influence_connect.db')}"


def _normalize_database_url(url: str) -> str:
    """Convert Supabase/Heroku postgres URLs for SQLAlchemy + psycopg2."""
    if not url:
        return url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _get_database_uri() -> str:
    if os.environ.get("USE_SQLITE", "").lower() in ("1", "true", "yes"):
        return _sqlite_uri()
    url = os.environ.get("DATABASE_URL")
    if url and any(p in url for p in ("[YOUR-PASSWORD]", "[PASSWORD]")):
        url = None
    if url:
        return _normalize_database_url(url)
    return _sqlite_uri()


def _database_reachable(uri: str) -> bool:
    if uri.startswith("sqlite"):
        return True
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(uri, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


def resolve_database_uri() -> str:
    """Pick Supabase URL from env, or fall back to SQLite if offline/unreachable."""
    uri = _get_database_uri()
    if uri.startswith("sqlite") or _database_reachable(uri):
        if not uri.startswith("sqlite"):
            print("[ok] Connected to Supabase Postgres")
        return uri

    print("[!] Supabase unreachable — falling back to local SQLite.")
    if ".supabase.co" in uri and ".pooler.supabase.com" not in uri:
        print("    Reason: the direct host 'db.<ref>.supabase.co' is IPv6-only and")
        print("    won't resolve on most home/Windows networks.")
        print("    Fix: in the Supabase dashboard open Project Settings -> Database ->")
        print("    'Connection string' -> Session pooler, and copy that URL into")
        print("    DATABASE_URL in .env (host looks like aws-0-<region>.pooler.supabase.com,")
        print("    user looks like postgres.<project-ref>).")
    return _sqlite_uri()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "influence-connect-dev-secret-key")

    # Profile photo uploads (images are downscaled server-side before storage)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 40 * 1024 * 1024  # 40 MB per request (raw phone photos)

    # Supabase project (REST / Auth API — optional for future features)
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

    SQLALCHEMY_DATABASE_URI = resolve_database_uri()

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

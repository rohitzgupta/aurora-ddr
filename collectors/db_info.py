from utils.db import execute_query


def _collect(conn):
    """
    Collect database and instance information.
    """

    database_info_sql = """
    SELECT
        current_database() AS database_name,
        current_user AS current_user,
        version() AS version,
        current_setting('TimeZone') AS timezone,
        now() AS current_time,
        pg_postmaster_start_time() AS startup_time
    """

    extension_sql = """
    SELECT
        extname,
        extversion
    FROM pg_extension
    ORDER BY extname
    """

    settings_sql = """
    SELECT
        name,
        setting
    FROM pg_settings
    WHERE name IN (
        'max_connections',
        'shared_buffers',
        'work_mem',
        'maintenance_work_mem',
        'effective_cache_size',
        'autovacuum',
        'autovacuum_max_workers',
        'autovacuum_naptime',
        'checkpoint_timeout',
        'max_wal_size',
        'wal_buffers'
    )
    ORDER BY name
    """

    database_size_sql = """
    SELECT
        pg_size_pretty(pg_database_size(current_database()))
        AS database_size
    """

    activity_sql = """
    SELECT
        COUNT(*) total_sessions,
        COUNT(*) FILTER (
            WHERE state='active'
        ) active_sessions
    FROM pg_stat_activity
    """

    info = execute_query(conn, database_info_sql)

    extensions = execute_query(conn, extension_sql)

    settings = execute_query(conn, settings_sql)

    database_size = execute_query(conn, database_size_sql)

    activity = execute_query(conn, activity_sql)

    return {
        "database": info[0] if info else {},
        "extensions": extensions,
        "settings": settings,
        "database_size": database_size[0]["database_size"]
            if database_size else "Unknown",
        "activity": activity[0]
            if activity else {}
    }


def collect(conn):

    try:
        return _collect(conn)

    except Exception as exc:
        return {
            "database": {},
            "extensions": [],
            "settings": [],
            "database_size": "Unknown",
            "activity": {},
            "errors": [
                str(exc)
            ]
        }

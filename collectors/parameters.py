from utils.db import execute_query


def _collect(conn):
    """
    Important PostgreSQL Configuration Parameters
    """

    parameter_sql = """
    SELECT

        name,

        setting AS raw_setting,

        unit,

        short_desc

    FROM pg_settings

    WHERE name IN
    (
        -- Connections

        'max_connections',
        'superuser_reserved_connections',

        -- Memory

        'shared_buffers',
        'work_mem',
        'maintenance_work_mem',
        'effective_cache_size',

        -- Vacuum

        'autovacuum',
        'autovacuum_max_workers',
        'autovacuum_naptime',
        'autovacuum_vacuum_threshold',
        'autovacuum_analyze_threshold',

        -- WAL

        'checkpoint_timeout',
        'max_wal_size',
        'wal_buffers',

        -- Logging

        'log_min_duration_statement',

        -- Parallelism

        'max_parallel_workers',
        'max_parallel_workers_per_gather'
    )

    ORDER BY name
    """

    parameters = execute_query(
        conn,
        parameter_sql
    )

    memory = []
    vacuum = []
    wal = []
    connections = []
    logging = []
    parallel = []

    for row in parameters:

        name = row["name"]
        
        # Logic to avoid duplication: if the raw setting already looks like it has units
        # or if units are absent, just show the raw setting.
        raw = str(row["raw_setting"])
        unit = row["unit"]
        
        row["setting"] = f"{raw} {unit}" if unit and unit not in raw else raw

        if name in (
            "max_connections",
            "superuser_reserved_connections"
        ):
            connections.append(row)

        elif name in (
            "shared_buffers",
            "work_mem",
            "maintenance_work_mem",
            "effective_cache_size"
        ):
            memory.append(row)

        elif name in (
            "autovacuum",
            "autovacuum_max_workers",
            "autovacuum_naptime",
            "autovacuum_vacuum_threshold",
            "autovacuum_analyze_threshold"
        ):
            vacuum.append(row)

        elif name in (
            "checkpoint_timeout",
            "max_wal_size",
            "wal_buffers"
        ):
            wal.append(row)

        elif name in (
            "log_min_duration_statement",
        ):
            logging.append(row)

        elif name in (
            "max_parallel_workers",
            "max_parallel_workers_per_gather"
        ):
            parallel.append(row)

    return {

        "connections":
            connections,

        "memory":
            memory,

        "vacuum":
            vacuum,

        "wal":
            wal,

        "logging":
            logging,

        "parallel":
            parallel
    }


def collect(conn):

    try:
        return _collect(conn)

    except Exception as exc:
        return {
            "connections": [],
            "memory": [],
            "vacuum": [],
            "wal": [],
            "logging": [],
            "parallel": [],
            "errors": [
                str(exc)
            ]
        }

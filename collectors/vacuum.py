from utils.db import execute_query


def _collect(conn):
    """
    Vacuum Analysis
    """

    #
    # Active Vacuum Operations
    #

    active_vacuum_sql = """
    SELECT

        p.pid,

        n.nspname
            AS schema_name,

        c.relname
            AS table_name,

        p.phase,

        p.heap_blks_total,

        p.heap_blks_scanned,

        p.heap_blks_vacuumed,

        ROUND(
            (
                p.heap_blks_scanned::numeric /
                NULLIF(
                    p.heap_blks_total,
                    0
                )
            ) * 100,
            2
        ) AS pct_scanned

    FROM pg_stat_progress_vacuum p

    JOIN pg_class c
        ON c.oid = p.relid

    JOIN pg_namespace n
        ON n.oid = c.relnamespace

    ORDER BY
        p.heap_blks_total DESC
    """

    #
    # Tables Requiring Vacuum
    #

    tables_requiring_vacuum_sql = """
    SELECT

        schemaname,

        relname,

        n_live_tup,

        n_dead_tup,

        ROUND(
            CASE
                WHEN n_live_tup = 0
                THEN 0
                ELSE
                    (
                        n_dead_tup::numeric /
                        n_live_tup
                    ) * 100
            END,
            2
        ) AS dead_tuple_pct,

        last_vacuum,

        last_autovacuum

    FROM pg_stat_user_tables

    ORDER BY
        n_dead_tup DESC

    LIMIT 20
    """

    #
    # Tables Requiring Analyze
    #

    tables_requiring_analyze_sql = """
    SELECT

        schemaname,

        relname,

        n_mod_since_analyze,

        last_analyze,

        last_autoanalyze

    FROM pg_stat_user_tables

    ORDER BY
        n_mod_since_analyze DESC

    LIMIT 20
    """

    #
    # Autovacuum Settings
    #

    autovacuum_settings_sql = """
    SELECT

        name,

        setting

    FROM pg_settings

    WHERE name IN
    (
        'autovacuum',
        'autovacuum_max_workers',
        'autovacuum_naptime',
        'autovacuum_vacuum_threshold',
        'autovacuum_analyze_threshold',
        'vacuum_cost_limit'
    )

    ORDER BY
        name
    """

    #
    # Vacuum Summary
    #

    vacuum_summary_sql = """
    SELECT

        COUNT(*) FILTER
        (
            WHERE n_dead_tup > 1000000
        )
        AS tables_with_high_dead_tuples,

        MAX(n_dead_tup)
        AS highest_dead_tuple_count

    FROM pg_stat_user_tables
    """

    active_vacuum = execute_query(
        conn,
        active_vacuum_sql
    )

    tables_requiring_vacuum = execute_query(
        conn,
        tables_requiring_vacuum_sql
    )

    tables_requiring_analyze = execute_query(
        conn,
        tables_requiring_analyze_sql
    )

    autovacuum_settings = execute_query(
        conn,
        autovacuum_settings_sql
    )

    vacuum_summary = execute_query(
        conn,
        vacuum_summary_sql
    )

    return {

        "summary":
            vacuum_summary[0]
            if vacuum_summary
            else {},

        "active_vacuum":
            active_vacuum,

        "tables_requiring_vacuum":
            tables_requiring_vacuum,

        "tables_requiring_analyze":
            tables_requiring_analyze,

        "autovacuum_settings":
            autovacuum_settings
    }


def collect(conn):

    try:
        return _collect(conn)

    except Exception as exc:
        return {
            "summary": {},
            "active_vacuum": [],
            "tables_requiring_vacuum": [],
            "tables_requiring_analyze": [],
            "autovacuum_settings": [],
            "errors": [
                str(exc)
            ]
        }

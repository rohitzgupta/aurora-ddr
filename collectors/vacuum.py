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
        
        pg_total_relation_size(relid) AS size_bytes,
        
        pg_size_pretty(pg_total_relation_size(relid)) AS table_size,

        COALESCE(n_live_tup, 0) AS n_live_tup,

        COALESCE(n_dead_tup, 0) AS n_dead_tup,

        ROUND(
            LEAST(100.0,
                (n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0)) * 100
            ),
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

        COALESCE(COUNT(*) FILTER
        (
            WHERE (n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0)) > 0.2
        ), 0) AS tables_with_high_dead_tuples,

        COALESCE(MAX(n_dead_tup), 0) AS highest_dead_tuple_count

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

    # Add severity to vacuum tables
    for table in tables_requiring_vacuum:
        pct = float(table.get("dead_tuple_pct", 0) or 0)
        dead_tuples = int(table.get("n_dead_tup", 0) or 0)
        size_bytes = int(table.get("size_bytes", 0) or 0)
        
        # Severity Badges for Dead Tuple %
        if pct > 20:
            table["severity_badge"] = "Red"
            table["status_class"] = "status-critical"
        elif pct > 10:
            table["severity_badge"] = "Yellow"
            table["status_class"] = "status-watch"
        else:
            table["severity_badge"] = "Green"
            table["status_class"] = "status-healthy"
            
        # Risk Level Logic (Operational Impact)
        # Prioritize large tables with bloat or extremely high percentage bloat
        if (size_bytes > 1024*1024*1024 and pct > 5) or pct > 50 or dead_tuples > 1000000:
            table["risk_level"] = "Critical"
        elif (size_bytes > 100*1024*1024 and pct > 10) or pct > 20:
            table["risk_level"] = "High"
        elif pct > 10 or dead_tuples > 50000:
            table["risk_level"] = "Warning"
        else:
            table["risk_level"] = "Low"

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

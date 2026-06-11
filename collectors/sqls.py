from utils.db import execute_query


def _pg_stat_statements_installed(conn):

    sql = """
    SELECT EXISTS (
        SELECT 1
        FROM pg_extension
        WHERE extname = 'pg_stat_statements'
    ) AS installed
    """

    result = execute_query(conn, sql)

    if not result:
        return False

    return result[0]["installed"]


def collect(conn):
    """
    SQL Performance Analysis
    """

    if not _pg_stat_statements_installed(conn):

        return {
            "enabled": False,
            "top_total_time": [],
            "top_avg_time": [],
            "top_calls": [],
            "top_rows": []
        }

    top_total_time_sql = """
    SELECT

        calls,

        ROUND(total_exec_time::numeric,2)
            AS total_exec_time_ms,

        ROUND(mean_exec_time::numeric,2)
            AS avg_exec_time_ms,

        rows,

        ROUND(
            CAST(
                    (
                   total_exec_time /
                     NULLIF(SUM(total_exec_time) OVER(),0)
                ) * 100
              AS numeric
            ),
         2
        ) AS pct_total_time,

        LEFT(query,1000) AS query

    FROM pg_stat_statements

    WHERE calls > 0

    ORDER BY total_exec_time DESC

    LIMIT 20
    """

    top_avg_time_sql = """
    SELECT

        calls,

        ROUND(total_exec_time::numeric,2)
            AS total_exec_time_ms,

        ROUND(mean_exec_time::numeric,2)
            AS avg_exec_time_ms,

        rows,

        LEFT(query,1000) AS query

    FROM pg_stat_statements

    WHERE calls >= 5

    ORDER BY mean_exec_time DESC

    LIMIT 20
    """

    top_calls_sql = """
    SELECT

        calls,

        ROUND(total_exec_time::numeric,2)
            AS total_exec_time_ms,

        ROUND(mean_exec_time::numeric,2)
            AS avg_exec_time_ms,

        rows,

        LEFT(query,1000) AS query

    FROM pg_stat_statements

    ORDER BY calls DESC

    LIMIT 20
    """

    top_rows_sql = """
    SELECT

        calls,

        rows,

        ROUND(total_exec_time::numeric,2)
            AS total_exec_time_ms,

        ROUND(mean_exec_time::numeric,2)
            AS avg_exec_time_ms,

        LEFT(query,1000) AS query

    FROM pg_stat_statements

    ORDER BY rows DESC

    LIMIT 20
    """

    top_total_time = execute_query(
        conn,
        top_total_time_sql
    )

    top_avg_time = execute_query(
        conn,
        top_avg_time_sql
    )

    top_calls = execute_query(
        conn,
        top_calls_sql
    )

    top_rows = execute_query(
        conn,
        top_rows_sql
    )

    return {

        "enabled": True,

        "top_total_time":
            top_total_time,

        "top_avg_time":
            top_avg_time,

        "top_calls":
            top_calls,

        "top_rows":
            top_rows
    }
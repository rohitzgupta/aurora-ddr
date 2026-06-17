from utils.db import execute_query


def _empty_result(error=None):

    errors = []

    if error:
        errors.append(error)

    return {
        "summary": {"blks_read": 0, "blks_hit": 0, "cache_hit_pct": 0, "temp_files": 0, "temp_bytes": 0, "temp_bytes_pretty": "0 B", "deadlocks": 0},
        "table_io": [],
        "index_io": [],
        "temp_sql": [],
        "errors": errors
    }


def collect(conn):
    """
    IO pressure and temporary spill indicators.
    """

    try:

        summary_sql = """
        SELECT

            COALESCE(blks_read, 0) AS blks_read,

            COALESCE(blks_hit, 0) AS blks_hit,

            ROUND(
                COALESCE(blks_hit, 0) * 100.0 /
                NULLIF(
                    COALESCE(blks_hit, 0) + COALESCE(blks_read, 0),
                    0
                ),
                2
            ) AS cache_hit_pct,

            COALESCE(temp_files, 0) AS temp_files,

            COALESCE(temp_bytes, 0) AS temp_bytes,

            pg_size_pretty(COALESCE(temp_bytes, 0))
                AS temp_bytes_pretty,

            COALESCE(deadlocks, 0) AS deadlocks

        FROM pg_stat_database

        WHERE datname = current_database()
        """

        table_io_sql = """
        SELECT

            schemaname,

            relname,

            COALESCE(heap_blks_read, 0) AS heap_blks_read,

            COALESCE(heap_blks_hit, 0) AS heap_blks_hit,

            COALESCE(idx_blks_read, 0) AS idx_blks_read,

            COALESCE(idx_blks_hit, 0) AS idx_blks_hit,

            COALESCE(toast_blks_read, 0) AS toast_blks_read,

            COALESCE(toast_blks_hit, 0) AS toast_blks_hit,

            COALESCE(tidx_blks_read, 0) AS tidx_blks_read,

            COALESCE(tidx_blks_hit, 0) AS tidx_blks_hit,

            (
                COALESCE(heap_blks_read, 0) +
                COALESCE(idx_blks_read, 0) +
                COALESCE(toast_blks_read, 0) +
                COALESCE(tidx_blks_read, 0)
            ) AS total_blks_read,

            COALESCE(
                ROUND(
                    (
                        heap_blks_hit +
                        idx_blks_hit +
                        toast_blks_hit +
                        tidx_blks_hit
                    ) * 100.0 /
                    NULLIF(
                        COALESCE(heap_blks_hit, 0) +
                        COALESCE(idx_blks_hit, 0) +
                        COALESCE(toast_blks_hit, 0) +
                        COALESCE(tidx_blks_hit, 0) +
                        COALESCE(heap_blks_read, 0) +
                        COALESCE(idx_blks_read, 0) +
                        COALESCE(toast_blks_read, 0) +
                        COALESCE(tidx_blks_read, 0),
                        0
                    ),
                    2
                ),
                0
            ) AS hit_pct

        FROM pg_statio_user_tables

        ORDER BY total_blks_read DESC

        LIMIT 20
        """

        index_io_sql = """
        SELECT

            schemaname,

            relname,

            indexrelname,

            COALESCE(idx_blks_read, 0) AS idx_blks_read,

            COALESCE(idx_blks_hit, 0) AS idx_blks_hit,

            COALESCE(
                ROUND(
                    COALESCE(idx_blks_hit, 0) * 100.0 /
                    NULLIF(
                        COALESCE(idx_blks_hit, 0) + COALESCE(idx_blks_read, 0),
                        0
                    ),
                    2
                ),
                0
            ) AS hit_pct

        FROM pg_statio_user_indexes

        ORDER BY idx_blks_read DESC

        LIMIT 20
        """

        temp_sql_enabled_sql = """
        SELECT EXISTS (
            SELECT 1
            FROM pg_extension
            WHERE extname = 'pg_stat_statements'
        ) AS installed
        """

        summary = execute_query(
            conn,
            summary_sql
        )

        table_io = execute_query(
            conn,
            table_io_sql
        )

        index_io = execute_query(
            conn,
            index_io_sql
        )

        temp_sql = []

        installed = execute_query(
            conn,
            temp_sql_enabled_sql
        )

        if installed and installed[0].get(
            "installed"
        ):

            temp_sql_query = """
            SELECT

                calls,

                temp_blks_read,

                temp_blks_written,

                ROUND(mean_exec_time::numeric,2)
                    AS avg_exec_time_ms,

                LEFT(query,1000) AS query

            FROM pg_stat_statements

            WHERE temp_blks_read > 0
               OR temp_blks_written > 0

            ORDER BY
                temp_blks_read + temp_blks_written DESC

            LIMIT 20
            """

            try:
                temp_sql = execute_query(
                    conn,
                    temp_sql_query
                )

            except Exception:
                temp_sql = []

        return {
            "summary":
                summary[0] if summary else {},
            "table_io":
                table_io,
            "index_io":
                index_io,
            "temp_sql":
                temp_sql,
            "errors":
                []
        }

    except Exception as exc:

        return _empty_result(
            str(exc)
        )

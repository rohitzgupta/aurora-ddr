from utils.db import execute_query


def _empty_result(error=None):

    errors = []

    if error:
        errors.append(error)

    return {
        "summary": {},
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

            blks_read,

            blks_hit,

            ROUND(
                blks_hit * 100.0 /
                NULLIF(
                    blks_hit + blks_read,
                    0
                ),
                2
            ) AS cache_hit_pct,

            temp_files,

            temp_bytes,

            pg_size_pretty(temp_bytes)
                AS temp_bytes_pretty,

            deadlocks

        FROM pg_stat_database

        WHERE datname = current_database()
        """

        table_io_sql = """
        SELECT

            schemaname,

            relname,

            heap_blks_read,

            heap_blks_hit,

            idx_blks_read,

            idx_blks_hit,

            toast_blks_read,

            toast_blks_hit,

            tidx_blks_read,

            tidx_blks_hit,

            (
                heap_blks_read +
                idx_blks_read +
                toast_blks_read +
                tidx_blks_read
            ) AS total_blks_read,

            ROUND(
                (
                    heap_blks_hit +
                    idx_blks_hit +
                    toast_blks_hit +
                    tidx_blks_hit
                ) * 100.0 /
                NULLIF(
                    heap_blks_hit +
                    idx_blks_hit +
                    toast_blks_hit +
                    tidx_blks_hit +
                    heap_blks_read +
                    idx_blks_read +
                    toast_blks_read +
                    tidx_blks_read,
                    0
                ),
                2
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

            idx_blks_read,

            idx_blks_hit,

            ROUND(
                idx_blks_hit * 100.0 /
                NULLIF(
                    idx_blks_hit + idx_blks_read,
                    0
                ),
                2
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

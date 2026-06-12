from utils.db import execute_query


def collect(conn):
    """
    Storage Analysis
    """

    try:

        #
        # Largest Tables
        #

        largest_tables_sql = """
        SELECT

            schemaname,

            relname,

            pg_size_pretty(
                pg_relation_size(
                    relid
                )
            ) AS table_size,

            pg_relation_size(
                relid
            ) AS table_size_bytes

        FROM pg_catalog.pg_statio_user_tables

        ORDER BY
            table_size_bytes DESC

        LIMIT 20
        """

        #
        # Largest Indexes
        #

        largest_indexes_sql = """
        SELECT

            schemaname,

            indexrelname,

            pg_size_pretty(
                pg_relation_size(
                    indexrelid
                )
            ) AS index_size,

            pg_relation_size(
                indexrelid
            ) AS index_size_bytes

        FROM pg_stat_user_indexes

        ORDER BY
            index_size_bytes DESC

        LIMIT 20
        """

        #
        # Largest Objects
        #

        largest_objects_sql = """
        SELECT

            n.nspname
                AS schema_name,

            c.relname
                AS object_name,

            pg_size_pretty(
                pg_total_relation_size(
                    c.oid
                )
            ) AS total_size,

            pg_total_relation_size(
                c.oid
            ) AS total_size_bytes

        FROM pg_class c

        JOIN pg_namespace n
            ON n.oid = c.relnamespace

        WHERE c.relkind = 'r'

        ORDER BY
            total_size_bytes DESC

        LIMIT 20
        """

        table_activity_sql = """
        SELECT

            schemaname,

            relname,

            seq_scan,

            seq_tup_read,

            idx_scan,

            idx_tup_fetch,

            n_live_tup,

            n_dead_tup

        FROM pg_stat_user_tables

        ORDER BY
            seq_tup_read DESC

        LIMIT 20
        """

        index_usage_sql = """
        SELECT

            schemaname,

            relname,

            indexrelname,

            idx_scan,

            idx_tup_read,

            idx_tup_fetch

        FROM pg_stat_user_indexes

        ORDER BY idx_scan DESC

        LIMIT 20
        """

        #
        # Storage Summary
        #

        storage_summary_sql = """
        SELECT

            COUNT(*)
                AS total_tables

        FROM pg_class

        WHERE relkind = 'r'
        """

        largest_tables = execute_query(
            conn,
            largest_tables_sql
        )

        largest_indexes = execute_query(
            conn,
            largest_indexes_sql
        )

        largest_objects = execute_query(
            conn,
            largest_objects_sql
        )

        table_activity = execute_query(
            conn,
            table_activity_sql
        )

        index_usage = execute_query(
            conn,
            index_usage_sql
        )

        storage_summary = execute_query(
            conn,
            storage_summary_sql
        )

        return {

            "summary":
                storage_summary[0]
                if storage_summary
                else {},

            "largest_tables":
                largest_tables,

            "largest_indexes":
                largest_indexes,

            "largest_objects":
                largest_objects,

            "table_activity":
                table_activity,

            "index_usage":
                index_usage,

            "errors":
                []
        }

    except Exception as exc:

        return {
            "summary": {},
            "largest_tables": [],
            "largest_indexes": [],
            "largest_objects": [],
            "table_activity": [],
            "index_usage": [],
            "errors": [
                str(exc)
            ]
        }

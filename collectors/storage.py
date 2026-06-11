from utils.db import execute_query


def collect(conn):
    """
    Storage Analysis
    """

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
            largest_objects
    }
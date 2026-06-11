from utils.db import execute_query


def collect(conn):
    """
    Wait Event Analysis
    """

    wait_event_summary_sql = """
    SELECT

        COALESCE(
            wait_event_type,
            'CPU'
        ) AS wait_event_type,

        COUNT(*) AS session_count

    FROM pg_stat_activity

    WHERE pid <> pg_backend_pid()

    GROUP BY wait_event_type

    ORDER BY session_count DESC
    """

    wait_event_detail_sql = """
    SELECT

        COALESCE(
            wait_event_type,
            'CPU'
        ) AS wait_event_type,

        COALESCE(
            wait_event,
            'Running'
        ) AS wait_event,

        COUNT(*) AS session_count

    FROM pg_stat_activity

    WHERE pid <> pg_backend_pid()

    GROUP BY
        wait_event_type,
        wait_event

    ORDER BY session_count DESC

    LIMIT 25
    """

    active_waiters_sql = """
    SELECT

        pid,

        usename,

        application_name,

        client_addr,

        state,

        wait_event_type,

        wait_event,

        now() - query_start AS duration,

        LEFT(query,1000) AS query

    FROM pg_stat_activity

    WHERE wait_event_type IS NOT NULL

    ORDER BY query_start

    LIMIT 50
    """

    wait_summary = execute_query(
        conn,
        wait_event_summary_sql
    )

    wait_details = execute_query(
        conn,
        wait_event_detail_sql
    )

    active_waiters = execute_query(
        conn,
        active_waiters_sql
    )

    return {

        "summary":
            wait_summary,

        "details":
            wait_details,

        "active_waiters":
            active_waiters
    }
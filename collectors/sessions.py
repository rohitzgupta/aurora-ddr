from utils.db import execute_query


LONG_TXN_THRESHOLD_MINUTES = 5


def collect(conn):
    """
    Session and transaction analysis.
    """

    summary_sql = """
    SELECT
        COUNT(*) AS total_sessions,

        COUNT(*) FILTER (
            WHERE state = 'active'
        ) AS active_sessions,

        COUNT(*) FILTER (
            WHERE state = 'idle'
        ) AS idle_sessions,

        COUNT(*) FILTER (
            WHERE state = 'idle in transaction'
        ) AS idle_in_transaction
    FROM pg_stat_activity
    """

    state_breakdown_sql = """
    SELECT
        COALESCE(state,'unknown') AS state,
        COUNT(*) AS count
    FROM pg_stat_activity
    GROUP BY state
    ORDER BY count DESC
    """

    application_sql = """
    SELECT
        COALESCE(application_name,'unknown')
            AS application_name,
        COUNT(*) AS count
    FROM pg_stat_activity
    GROUP BY application_name
    ORDER BY count DESC
    LIMIT 20
    """

    host_sql = """
    SELECT
        COALESCE(client_addr::text,'local')
            AS client_host,
        COUNT(*) AS count
    FROM pg_stat_activity
    GROUP BY client_addr
    ORDER BY count DESC
    LIMIT 20
    """

    active_sessions_sql = """
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

    WHERE state = 'active'

    ORDER BY query_start

    LIMIT 50
    """

    long_running_txn_sql = """
    SELECT
        pid,
        usename,
        application_name,

        state,

        wait_event_type,
        wait_event,

        now() - xact_start AS duration,

        LEFT(query,1000) AS query

    FROM pg_stat_activity

    WHERE xact_start IS NOT NULL

    AND now() - xact_start >
        interval '5 minutes'

    ORDER BY xact_start
    """

    summary = execute_query(
        conn,
        summary_sql
    )

    states = execute_query(
        conn,
        state_breakdown_sql
    )

    applications = execute_query(
        conn,
        application_sql
    )

    hosts = execute_query(
        conn,
        host_sql
    )

    active_sessions = execute_query(
        conn,
        active_sessions_sql
    )

    long_running_transactions = execute_query(
        conn,
        long_running_txn_sql
    )

    return {
        "summary":
            summary[0] if summary else {},

        "state_breakdown":
            states,

        "applications":
            applications,

        "hosts":
            hosts,

        "active_sessions":
            active_sessions,

        "long_running_transactions":
            long_running_transactions
    }
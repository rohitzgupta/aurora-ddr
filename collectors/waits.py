from utils.db import execute_query


def _empty_result(error=None):

    errors = []

    if error:
        errors.append(error)

    return {

        "summary":
            [],

        "details":
            [],

        "active_waiters":
            [],

        "summary_metrics":
            {
                "total_sessions_observed": 0,
                "waiting_sessions": 0,
                "active_waiting_sessions": 0,
                "top_wait_event_type": None,
                "top_wait_event": None,
                "top_wait_session_count": 0
            },

        "errors":
            errors
    }


def collect(conn):
    """
    Wait Event Analysis
    """

    try:

        wait_event_summary_sql = """
        SELECT

            COALESCE(
                wait_event_type,
                'CPU'
            ) AS wait_event_type,

            COUNT(*) AS session_count,

            COUNT(*) FILTER (
                WHERE wait_event_type IS NOT NULL
            ) AS waiting_count,

            COUNT(*) FILTER (
                WHERE state = 'active'
                  AND wait_event_type IS NOT NULL
            ) AS active_waiting_count,

            ROUND(
                COUNT(*) * 100.0 /
                NULLIF(
                    SUM(COUNT(*)) OVER (),
                    0
                ),
                2
            ) AS pct_sessions

        FROM pg_stat_activity

        WHERE pid <> pg_backend_pid()
          AND COALESCE(state, '') <> 'idle'

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

            COUNT(*) AS session_count,

            COUNT(*) FILTER (
                WHERE state = 'active'
            ) AS active_count,

            ROUND(
                COUNT(*) * 100.0 /
                NULLIF(
                    SUM(COUNT(*)) OVER (),
                    0
                ),
                2
            ) AS pct_sessions

        FROM pg_stat_activity

        WHERE pid <> pg_backend_pid()
          AND COALESCE(state, '') <> 'idle'

        GROUP BY
            wait_event_type,
            wait_event

        ORDER BY
            session_count DESC,
            active_count DESC

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

            now() - xact_start AS transaction_duration,

            LEFT(query,1000) AS query

        FROM pg_stat_activity

        WHERE wait_event_type IS NOT NULL
          AND pid <> pg_backend_pid()
          AND COALESCE(state, '') <> 'idle'

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

        total_sessions_observed = sum(
            row.get(
                "session_count",
                0
            )
            for row in wait_summary
        )

        waiting_sessions = sum(
            row.get(
                "waiting_count",
                0
            )
            for row in wait_summary
        )

        active_waiting_sessions = sum(
            row.get(
                "active_waiting_count",
                0
            )
            for row in wait_summary
        )

        top_wait = {}

        if wait_details:
            top_wait = wait_details[0]

        return {

            "summary":
                wait_summary,

            "details":
                wait_details,

            "active_waiters":
                active_waiters,

            "summary_metrics":
                {
                    "total_sessions_observed":
                        total_sessions_observed,

                    "waiting_sessions":
                        waiting_sessions,

                    "active_waiting_sessions":
                        active_waiting_sessions,

                    "top_wait_event_type":
                        top_wait.get(
                            "wait_event_type"
                        ),

                    "top_wait_event":
                        top_wait.get(
                            "wait_event"
                        ),

                    "top_wait_session_count":
                        top_wait.get(
                            "session_count",
                            0
                        )
                },

            "errors":
                []
        }

    except Exception as exc:

        return _empty_result(
            str(exc)
        )

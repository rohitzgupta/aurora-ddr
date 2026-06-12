from utils.db import execute_query


def _collect(conn):
    """
    Lock and blocking analysis.
    """

    waiting_sessions_sql = """
    SELECT

        blocked.pid AS blocked_pid,
        blocked.usename AS blocked_user,
        blocked.application_name AS blocked_application,

        blocker.pid AS blocker_pid,
        blocker.usename AS blocker_user,
        blocker.application_name AS blocker_application,

        now() - blocked.query_start AS wait_duration,

        blocked.wait_event_type,
        blocked.wait_event,

        LEFT(blocked.query,1000)
            AS blocked_query,

        LEFT(blocker.query,1000)
            AS blocker_query

    FROM pg_stat_activity blocked

    JOIN pg_locks blocked_locks
        ON blocked.pid = blocked_locks.pid

    JOIN pg_locks blocker_locks
        ON blocked_locks.locktype =
           blocker_locks.locktype

        AND blocked_locks.database
            IS NOT DISTINCT FROM
            blocker_locks.database

        AND blocked_locks.relation
            IS NOT DISTINCT FROM
            blocker_locks.relation

        AND blocked_locks.page
            IS NOT DISTINCT FROM
            blocker_locks.page

        AND blocked_locks.tuple
            IS NOT DISTINCT FROM
            blocker_locks.tuple

        AND blocked_locks.transactionid
            IS NOT DISTINCT FROM
            blocker_locks.transactionid

        AND blocked_locks.classid
            IS NOT DISTINCT FROM
            blocker_locks.classid

        AND blocked_locks.objid
            IS NOT DISTINCT FROM
            blocker_locks.objid

        AND blocked_locks.objsubid
            IS NOT DISTINCT FROM
            blocker_locks.objsubid

    JOIN pg_stat_activity blocker
        ON blocker.pid =
           blocker_locks.pid

    WHERE NOT blocked_locks.granted
      AND blocker_locks.granted

    ORDER BY wait_duration DESC
    """

    lock_summary_sql = """
    SELECT
        locktype,
        mode,
        COUNT(*) AS count
    FROM pg_locks
    GROUP BY
        locktype,
        mode
    ORDER BY count DESC
    """

    active_lock_count_sql = """
    SELECT
        COUNT(*) AS active_locks
    FROM pg_locks
    """

    waiting_sessions = execute_query(
        conn,
        waiting_sessions_sql
    )

    lock_summary = execute_query(
        conn,
        lock_summary_sql
    )

    active_lock_count = execute_query(
        conn,
        active_lock_count_sql
    )

    blocker_pids = set()

    for row in waiting_sessions:
        blocker_pids.add(
            row["blocker_pid"]
        )

    summary = {

        "blocked_sessions":
            len(waiting_sessions),

        "blocking_sessions":
            len(blocker_pids),

        "active_locks":
            active_lock_count[0]["active_locks"]
            if active_lock_count else 0
    }

    blocking_sessions = []

    for blocker_pid in blocker_pids:

        sql = f"""
        SELECT

            pid,
            usename,
            application_name,

            state,

            now() - xact_start
                AS transaction_duration,

            wait_event_type,
            wait_event,

            LEFT(query,1000)
                AS query

        FROM pg_stat_activity

        WHERE pid = {blocker_pid}
        """

        rows = execute_query(
            conn,
            sql
        )

        if rows:
            blocking_sessions.append(
                rows[0]
            )

    return {

        "summary":
            summary,

        "waiting_sessions":
            waiting_sessions,

        "blocking_sessions":
            blocking_sessions,

        "lock_summary":
            lock_summary
    }


def collect(conn):

    try:
        return _collect(conn)

    except Exception as exc:
        return {
            "summary": {
                "blocked_sessions": 0,
                "blocking_sessions": 0,
                "active_locks": 0
            },
            "waiting_sessions": [],
            "blocking_sessions": [],
            "lock_summary": [],
            "errors": [
                str(exc)
            ]
        }

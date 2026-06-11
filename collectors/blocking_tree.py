from utils.db import execute_query


def collect(conn):
    """
    Blocking Tree Analysis
    """

    sql = """
    SELECT

        pid,

        usename,

        application_name,

        state,

        now() - xact_start
            AS transaction_duration,

        pg_blocking_pids(pid)
            AS blocking_pids,

        LEFT(query,1000)
            AS query

    FROM pg_stat_activity

    WHERE array_length(
        pg_blocking_pids(pid),
        1
    ) > 0
    """

    rows = execute_query(
        conn,
        sql
    )

    tree = []

    for row in rows:

        blockers = row.get(
            "blocking_pids",
            []
        )

        tree.append({

            "blocked_pid":
                row["pid"],

            "blocked_user":
                row["usename"],

            "blocking_pids":
                blockers,

            "duration":
                row[
                    "transaction_duration"
                ],

            "query":
                row["query"]
        })

    return {

        "blocked_count":
            len(tree),

        "tree":
            tree
    }
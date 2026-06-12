def _collect(
    db_info,
    sessions,
    locks,
    sqls,
    waits,
    freeze_age
):
    """
    Generate Executive Findings
    """

    findings = []

    critical_count = 0
    warning_count = 0
    info_count = 0

    #
    # Blocking Sessions
    #

    blocked_sessions = (
        locks.get("summary", {})
        .get("blocked_sessions", 0)
    )

    if blocked_sessions > 0:

        findings.append({

            "severity": "CRITICAL",

            "title":
                "Blocked Sessions Detected",

            "message":
                f"{blocked_sessions} session(s) "
                f"currently waiting on locks."
        })

        critical_count += 1

    #
    # Lock Wait Pressure
    #

    wait_summary = waits.get(
        "summary",
        []
    )

    for row in wait_summary:

        if (
            row.get(
                "wait_event_type"
            )
            == "Lock"
            and
            row.get(
                "session_count",
                0
            ) >= 5
        ):

            findings.append({

                "severity": "CRITICAL",

                "title":
                    "Lock Wait Pressure",

                "message":
                    f"{row.get('session_count', 0)} "
                    f"sessions currently "
                    f"waiting on locks."
            })

            critical_count += 1

            break

    #
    # IO Wait Pressure
    #

    for row in wait_summary:

        if (
            row.get(
                "wait_event_type"
            )
            == "IO"
            and
            row.get(
                "session_count",
                0
            ) > 0
        ):

            findings.append({

                "severity": "WARNING",

                "title":
                    "IO Waits Detected",

                "message":
                    f"{row.get('session_count', 0)} "
                    f"non-idle session(s) are "
                    f"waiting on IO."
            })

            warning_count += 1

            break

    #
    # BufferPin Wait Pressure
    #

    for row in wait_summary:

        if (
            row.get(
                "wait_event_type"
            )
            == "BufferPin"
            and
            row.get(
                "session_count",
                0
            ) > 0
        ):

            findings.append({

                "severity": "WARNING",

                "title":
                    "BufferPin Waits Detected",

                "message":
                    f"{row.get('session_count', 0)} "
                    f"non-idle session(s) are "
                    f"waiting on BufferPin events."
            })

            warning_count += 1

            break

    #
    # LWLock Wait Pressure
    #

    for row in wait_summary:

        if (
            row.get(
                "wait_event_type"
            )
            == "LWLock"
            and
            row.get(
                "session_count",
                0
            ) > 0
        ):

            findings.append({

                "severity": "WARNING",

                "title":
                    "LWLock Waits Detected",

                "message":
                    f"{row.get('session_count', 0)} "
                    f"non-idle session(s) are "
                    f"waiting on lightweight locks."
            })

            warning_count += 1

            break

    #
    # Freeze Age Critical
    #

    freeze_critical = (
        freeze_age
        .get("summary", {})
        .get("critical_tables", 0)
    )

    if freeze_critical > 0:

        findings.append({

            "severity": "CRITICAL",

            "title":
                "Frozen Transaction ID Risk",

            "message":
                f"{freeze_critical} table(s) "
                f"exceeded freeze age "
                f"threshold of 500M."
        })

        critical_count += 1

    #
    # Freeze Age Warning
    #

    freeze_warning = (
        freeze_age
        .get("summary", {})
        .get("warning_tables", 0)
    )

    if (
        freeze_warning > 0
        and
        freeze_critical == 0
    ):

        findings.append({

            "severity": "WARNING",

            "title":
                "Elevated Freeze Age",

            "message":
                f"{freeze_warning} table(s) "
                f"exceeded freeze age "
                f"warning threshold of 200M."
        })

        warning_count += 1

    #
    # Long Running Transactions
    #

    long_txn_count = len(
        sessions.get(
            "long_running_transactions",
            []
        )
    )

    if long_txn_count > 0:

        findings.append({

            "severity": "WARNING",

            "title":
                "Long Running Transactions",

            "message":
                f"{long_txn_count} "
                f"transaction(s) running "
                f"longer than 5 minutes."
        })

        warning_count += 1

    #
    # Idle In Transaction
    #

    idle_in_txn = (
        sessions.get("summary", {})
        .get(
            "idle_in_transaction",
            0
        )
    )

    if idle_in_txn >= 5:

        findings.append({

            "severity": "WARNING",

            "title":
                "Idle In Transaction Sessions",

            "message":
                f"{idle_in_txn} session(s) "
                f"are idle in transaction."
        })

        warning_count += 1

    #
    # High Active Session Ratio
    #

    active_sessions = (
        sessions.get("summary", {})
        .get(
            "active_sessions",
            0
        )
    )

    total_sessions = (
        sessions.get("summary", {})
        .get(
            "total_sessions",
            0
        )
    )

    if (
        total_sessions > 0
        and
        active_sessions >
        (total_sessions * 0.80)
    ):

        findings.append({

            "severity": "WARNING",

            "title":
                "High Active Session Ratio",

            "message":
                f"{active_sessions} of "
                f"{total_sessions} sessions "
                f"are active."
        })

        warning_count += 1

    #
    # pg_stat_statements
    #

    if not sqls.get(
        "enabled",
        False
    ):

        findings.append({

            "severity": "WARNING",

            "title":
                "pg_stat_statements Missing",

            "message":
                "Top SQL analysis "
                "is unavailable."
        })

        warning_count += 1

    #
    # Database Size
    #

    findings.append({

        "severity": "INFO",

        "title":
            "Database Size",

        "message":
            db_info.get(
                "database_size",
                "Unknown"
            )
    })

    info_count += 1

    #
    # Healthy Database
    #

    if (
        critical_count == 0
        and
        warning_count == 0
    ):

        findings.insert(

            0,

            {

                "severity": "INFO",

                "title":
                    "No Critical Issues Found",

                "message":
                    "No blocking sessions, "
                    "lock pressure, freeze age "
                    "or transaction issues detected."
            }
        )

        info_count += 1

    return {

        "critical_count":
            critical_count,

        "warning_count":
            warning_count,

        "info_count":
            info_count,

        "findings":
            findings
    }


def collect(
    db_info,
    sessions,
    locks,
    sqls,
    waits,
    freeze_age
):

    try:
        return _collect(
            db_info,
            sessions,
            locks,
            sqls,
            waits,
            freeze_age
        )

    except Exception as exc:
        return {
            "critical_count": 0,
            "warning_count": 1,
            "info_count": 0,
            "findings": [
                {
                    "severity": "WARNING",
                    "title": "Findings Generation Incomplete",
                    "message": str(exc)
                }
            ]
        }

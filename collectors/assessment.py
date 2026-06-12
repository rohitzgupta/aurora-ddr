def _risk(
    severity,
    title,
    evidence,
    impact,
    action,
    owner
):
    return {
        "severity": severity,
        "title": title,
        "evidence": evidence,
        "impact": impact,
        "action": action,
        "owner": owner
    }


def _recommendation(
    priority,
    title,
    action,
    owner
):
    return {
        "priority": priority,
        "title": title,
        "action": action,
        "owner": owner
    }


def _score_status(score):

    if score >= 90:
        return ("Healthy", "status-healthy")

    if score >= 75:
        return ("Watch", "status-watch")

    if score >= 60:
        return ("Elevated Risk", "status-elevated")

    if score >= 40:
        return ("High Risk", "status-high")

    return ("Critical", "status-critical")


def collect(
    db_info,
    sessions,
    locks,
    sqls,
    waits,
    blocking_tree,
    vacuum,
    freeze_age,
    storage,
    io
):
    """
    Executive point-in-time health assessment.
    """

    try:

        risks = []
        recommendations = []
        score = 100

        session_summary = sessions.get(
            "summary",
            {}
        )

        wait_summary = waits.get(
            "summary",
            []
        )

        wait_metrics = waits.get(
            "summary_metrics",
            {}
        )

        lock_summary = locks.get(
            "summary",
            {}
        )

        blocked_sessions = lock_summary.get(
            "blocked_sessions",
            0
        )

        if blocked_sessions > 0:
            score -= 25
            risks.append(_risk(
                "CRITICAL",
                "Blocking Sessions Are Present",
                f"{blocked_sessions} blocked session(s)",
                "User transactions may be stalled behind a blocker.",
                "Review the blocking tree and resolve the blocker before tuning SQL.",
                "DBA / App Team"
            ))
            recommendations.append(_recommendation(
                "Now",
                "Resolve Blocking Chain",
                "Identify the root blocker PID, review its SQL and transaction age, then coordinate rollback/commit/termination if required.",
                "DBA"
            ))

        wait_counts = {}

        for row in wait_summary:
            wait_counts[
                row.get(
                    "wait_event_type"
                )
            ] = row.get(
                "session_count",
                0
            )

        if wait_counts.get("Lock", 0) > 0:
            score -= 15
            risks.append(_risk(
                "CRITICAL",
                "Lock Waits Are Slowing Work",
                f"{wait_counts.get('Lock', 0)} non-idle session(s) on Lock waits",
                "Concurrent work may be queued behind row, transaction, or table locks.",
                "Use Blocking Analysis to find the blocker and review application transaction boundaries.",
                "DBA / App Team"
            ))

        if wait_counts.get("IO", 0) > 0:
            score -= 10
            risks.append(_risk(
                "WARNING",
                "IO Waits Detected",
                f"{wait_counts.get('IO', 0)} non-idle session(s) on IO waits",
                "Queries may be waiting on storage reads or writes.",
                "Review IO Pressure and top SQL for high read, write, or temp activity.",
                "DBA / Infra"
            ))

        if wait_counts.get("BufferPin", 0) > 0:
            score -= 10
            risks.append(_risk(
                "WARNING",
                "BufferPin Waits Detected",
                f"{wait_counts.get('BufferPin', 0)} non-idle session(s)",
                "Queries may be waiting for another backend to release a pinned buffer.",
                "Check long-running readers, writers, and active SQL touching the same objects.",
                "DBA"
            ))

        if wait_counts.get("LWLock", 0) > 0:
            score -= 10
            risks.append(_risk(
                "WARNING",
                "LWLock Contention Detected",
                f"{wait_counts.get('LWLock', 0)} non-idle session(s)",
                "Internal lightweight lock contention may be limiting throughput.",
                "Review wait event details, WAL/checkpoint indicators, and high-concurrency SQL.",
                "DBA"
            ))

        long_txn_count = len(
            sessions.get(
                "long_running_transactions",
                []
            )
        )

        if long_txn_count > 0:
            score -= 10
            risks.append(_risk(
                "WARNING",
                "Long-Running Transactions",
                f"{long_txn_count} transaction(s) older than 5 minutes",
                "Old transactions can hold locks and delay cleanup.",
                "Review long transactions and idle-in-transaction sessions before deeper tuning.",
                "DBA / App Team"
            ))

        idle_in_txn = session_summary.get(
            "idle_in_transaction",
            0
        )

        if idle_in_txn >= 5:
            score -= 10
            risks.append(_risk(
                "WARNING",
                "Idle-In-Transaction Pressure",
                f"{idle_in_txn} session(s) idle in transaction",
                "Open transactions can block vacuum and retain locks.",
                "Inspect application connection handling and transaction lifecycle.",
                "App Team"
            ))

        active_sessions = session_summary.get(
            "active_sessions",
            0
        )

        total_sessions = session_summary.get(
            "total_sessions",
            0
        )

        active_ratio = 0

        if total_sessions:
            active_ratio = round(
                (active_sessions / total_sessions) * 100,
                2
            )

        if total_sessions > 0 and active_ratio >= 80:
            score -= 10
            risks.append(_risk(
                "WARNING",
                "High Active Session Ratio",
                f"{active_sessions} of {total_sessions} sessions active",
                "The database may be saturated by concurrent active work.",
                "Review top waits and active SQL before adding capacity.",
                "DBA"
            ))

        freeze_summary = freeze_age.get(
            "summary",
            {}
        )

        freeze_critical = freeze_summary.get(
            "critical_tables",
            0
        )

        freeze_warning = freeze_summary.get(
            "warning_tables",
            0
        )

        if freeze_critical > 0:
            score -= 25
            risks.append(_risk(
                "CRITICAL",
                "Transaction ID Freeze Risk",
                f"{freeze_critical} table(s) above critical freeze age",
                "Database availability can be at risk if freeze age is not controlled.",
                "Prioritize vacuum/freeze remediation for critical tables.",
                "DBA"
            ))

        elif freeze_warning > 0:
            score -= 10
            risks.append(_risk(
                "WARNING",
                "Elevated Freeze Age",
                f"{freeze_warning} table(s) above warning threshold",
                "Autovacuum may be falling behind on transaction ID cleanup.",
                "Review freeze-age tables and autovacuum configuration.",
                "DBA"
            ))

        vacuum_summary = vacuum.get(
            "summary",
            {}
        )

        high_dead = vacuum_summary.get(
            "tables_with_high_dead_tuples",
            0
        ) or 0

        if high_dead > 0:
            score -= 10
            risks.append(_risk(
                "WARNING",
                "Dead Tuple Buildup",
                f"{high_dead} table(s) with high dead tuples",
                "Bloat and stale visibility can increase IO and query latency.",
                "Review vacuum candidates and autovacuum settings.",
                "DBA"
            ))

        io_summary = io.get(
            "summary",
            {}
        )

        temp_bytes = io_summary.get(
            "temp_bytes",
            0
        ) or 0

        if temp_bytes > 0:
            score -= 5
            risks.append(_risk(
                "INFO",
                "Temporary File Activity Present",
                io_summary.get(
                    "temp_bytes_pretty",
                    "Temp usage detected"
                ),
                "Sorts, hashes, or large joins may be spilling to temporary files.",
                "Review temp-heavy SQL and memory settings such as work_mem.",
                "DBA / App Team"
            ))

        if not sqls.get(
            "enabled",
            False
        ):
            score -= 10
            risks.append(_risk(
                "WARNING",
                "SQL Visibility Is Limited",
                "pg_stat_statements is not installed",
                "The report cannot identify the highest-load SQL reliably.",
                "Enable pg_stat_statements for future root-cause analysis.",
                "DBA"
            ))
            recommendations.append(_recommendation(
                "Today",
                "Enable SQL Workload Visibility",
                "Enable pg_stat_statements in a controlled maintenance path so future reports can identify top SQL.",
                "DBA"
            ))

        if not risks:
            risks.append(_risk(
                "INFO",
                "No Immediate Point-In-Time Risk Detected",
                "No blocking, major wait, freeze, or transaction pressure found",
                "No active slowdown root cause is visible in current database statistics.",
                "Use CloudWatch or Performance Insights if users reported a past slowdown.",
                "DBA"
            ))

        if not recommendations:
            recommendations.append(_recommendation(
                "Monitor",
                "Continue Point-In-Time Monitoring",
                "No urgent corrective action is visible in the current PostgreSQL statistics.",
                "DBA"
            ))

        score = max(
            0,
            min(
                100,
                score
            )
        )

        status, status_class = _score_status(
            score
        )

        return {
            "score": score,
            "status": status,
            "status_class": status_class,
            "active_ratio": active_ratio,
            "top_wait_event_type": wait_metrics.get(
                "top_wait_event_type"
            ),
            "top_wait_event": wait_metrics.get(
                "top_wait_event"
            ),
            "risks": risks[:8],
            "recommendations": recommendations[:8],
            "limitations": [
                "Point-in-time assessment only",
                "No historical baseline or AWR-style snapshots",
                "Aurora host-level CPU and storage latency require AWS metrics"
            ],
            "errors": []
        }

    except Exception as exc:

        return {
            "score": 0,
            "status": "Assessment Incomplete",
            "status_class": "status-critical",
            "active_ratio": 0,
            "top_wait_event_type": None,
            "top_wait_event": None,
            "risks": [],
            "recommendations": [],
            "limitations": [
                "Assessment failed before scoring could complete"
            ],
            "errors": [
                str(exc)
            ]
        }

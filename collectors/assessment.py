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


def _generate_root_causes(score, deductions, wait_counts, session_summary, io_summary, freeze_summary, vacuum_summary):
    """
    Generates the Probable Root Cause Assessment based on weighted evidence.
    """
    causes = []
    
    # Connection Pressure
    util = session_summary.get("utilization", 0)
    if util > 70:
        causes.append({
            "contributor": "Connection Pressure",
            "confidence": "High" if util > 90 else "Medium" if util > 70 else "Low",
            "evidence": f"{util}% of max_connections utilized ({session_summary.get('total_sessions')} sessions).",
            "investigation": "Check application connection pool settings and scale or optimize session lifecycle."
        })

    # Lock Waits
    lock_waiters = wait_counts.get("Lock", 0)
    if lock_waiters > 0:
        causes.append({
            "contributor": "Lock Contention",
            "confidence": "High" if lock_waiters > 5 else "Medium" if lock_waiters > 0 else "Low",
            "evidence": f"{lock_waiters} session(s) blocked on heavy-weight locks.",
            "investigation": "Review the Blocking Tree to identify the root blocker and the SQL holding locks."
        })

    # IO Waits
    io_waiters = wait_counts.get("IO", 0)
    if io_waiters > 0:
        causes.append({
            "contributor": "IO Saturation",
            "confidence": "Medium" if io_waiters > 2 else "Low",
            "evidence": f"{io_waiters} session(s) waiting on storage reads/writes.",
            "investigation": "Identify high-IO SQL queries and check Aurora storage latency metrics."
        })

    # LWLock Contention
    lw_waiters = wait_counts.get("LWLock", 0)
    if lw_waiters > 0:
        causes.append({
            "contributor": "LWLock Contention",
            "confidence": "Medium" if lw_waiters > 2 else "Low",
            "evidence": f"{lw_waiters} session(s) waiting on internal light-weight locks.",
            "investigation": "Check for high concurrency on specific pages or WAL write pressure."
        })

    # Idle In Transaction
    itx = session_summary.get("idle_in_transaction", 0)
    if itx >= 5:
        causes.append({
            "contributor": "Idle In Transaction",
            "confidence": "High",
            "evidence": f"{itx} sessions holding transactions open without active work.",
            "investigation": "Audit application code for missing commits/rollbacks and connection handling."
        })

    # Blocking (Top priority if exists)
    blocked = deductions.count("-25: Active blocking sessions detected")
    if blocked > 0:
        causes.append({
            "contributor": "Heavy Blocking",
            "confidence": "High",
            "evidence": "Active blocking chain detected in pg_locks.",
            "investigation": "Use the Blocking Tree to find the root blocker and terminate if necessary."
        })

    # Temp Spills
    temp_bytes = io_summary.get("temp_bytes", 0) or 0
    if temp_bytes > 1024 * 1024 * 512: # > 512MB
        causes.append({
            "contributor": "Temporary File Spills",
            "confidence": "High",
            "evidence": io_summary.get("temp_bytes_pretty") or "High temp usage",
            "investigation": "Review Top SQL for large sorts/joins and consider increasing work_mem."
        })

    # Vacuum Pressure
    dead_tables = vacuum_summary.get("tables_with_high_dead_tuples", 0)
    if dead_tables > 0:
        causes.append({
            "contributor": "Vacuum Pressure",
            "confidence": "Medium",
            "evidence": f"{dead_tables} table(s) with significant dead tuple buildup.",
            "investigation": "Check autovacuum settings and identify if long-running transactions are blocking cleanup."
        })

    # TXID Freeze Risk
    if freeze_summary.get("critical_tables", 0) > 0:
        causes.append({
            "contributor": "TXID Freeze Risk",
            "confidence": "High",
            "evidence": f"{freeze_summary.get('critical_tables')} tables approaching wraparound.",
            "investigation": "Perform emergency manual VACUUM FREEZE on critical tables."
        })

    # Sort by weight/confidence and prioritize high-impact contributors
    confidence_map = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "N/A": 0}
    sorted_causes = sorted(causes, key=lambda x: (confidence_map.get(x['confidence'], 0), x['contributor']), reverse=True)
    
    if not sorted_causes:
        sorted_causes.append({
            "contributor": "Healthy Workload",
            "confidence": "N/A",
            "evidence": "No significant performance bottlenecks detected in current stats.",
            "investigation": "Continue monitoring or check historical CloudWatch metrics."
        })

    return sorted_causes[:3]


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
        deductions = []

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

        # Connection Utilization Calculation
        max_conns = int(db_info.get("settings_dict", {}).get("max_connections") or 0)
        total_sessions = session_summary.get("total_sessions") or 0
        conn_util = round((total_sessions / max_conns * 100), 2) if max_conns > 0 else 0
        session_summary["utilization"] = conn_util
        session_summary["max_connections"] = max_conns
        
        if conn_util > 90:
            score -= 20
            deductions.append("-20: Critical Connection Utilization")
            session_summary["utilization_status"] = "High"
            risks.append(_risk("CRITICAL", "Connection Saturation", f"{conn_util}% utilized", "Database may reject new connections.", "Increase max_connections or use a connection pooler.", "DBA"))
        elif conn_util > 70:
            score -= 10
            deductions.append("-10: High Connection Utilization")
            session_summary["utilization_status"] = "Watch"
            risks.append(_risk("WARNING", "High Connection Count", f"{conn_util}% utilized", "Approaching connection limits.", "Review connection pooling and idle session timeouts.", "DBA"))
        else:
            session_summary["utilization_status"] = "Healthy"

        # Deductions based on data
        io_summary = io.get("summary", {})
        freeze_summary = freeze_age.get("summary", {})
        vacuum_summary = vacuum.get("summary", {})
        
        # Logic for Why the score was assigned
        if score == 100:
            score_explanation = "The database is operating within healthy parameters with no significant issues detected."
        elif score >= 90:
            score_explanation = "The database is generally healthy, with minor observations that do not currently impact availability."
        else:
            score_explanation = f"The score of {score} reflects detected performance bottlenecks or resource pressures that require attention."

        blocked_sessions = lock_summary.get(
            "blocked_sessions",
            0
        )

        if blocked_sessions > 0:
            score -= 25
            deductions.append("-25: Critical Table Blocking")
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
            deductions.append("-15: Lock Contention")
            risks.append(_risk(
                "CRITICAL",
                "Lock Waits Are Slowing Work",
                f"{wait_counts.get('Lock', 0)} non-idle session(s) on Lock waits",
                "Concurrent work may be queued behind row, transaction, or table locks.",
                "Use Blocking Analysis to find the blocker and review application transaction boundaries.",
                "DBA / App Team"
            ))
            recommendations.append(_recommendation(
                "Now",
                "Investigate Lock Contention",
                "Identify blocking PIDs and check for long-held row or table locks.",
                "DBA"
            ))

        if wait_counts.get("IO", 0) > 0:
            score -= 10
            deductions.append("-10: IO Wait Pressure")
            risks.append(_risk(
                "WARNING",
                "IO Waits Detected",
                f"{wait_counts.get('IO', 0)} non-idle session(s) on IO waits",
                "Queries may be waiting on storage reads or writes.",
                "Review IO Pressure and top SQL for high read, write, or temp activity.",
                "DBA / Infra"
            ))
            recommendations.append(_recommendation(
                "Today",
                "Perform IO Investigation",
                "Check for disk saturation or high-IO SQL queries.",
                "DBA"
            ))

        if wait_counts.get("BufferPin", 0) > 0:
            score -= 10
            deductions.append("-10: BufferPin Contention")
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
            deductions.append("-10: Internal Concurrency (LWLock)")
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
            deductions.append("-10: Long Transactions")
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
            deductions.append("-10: Excessive Idle-in-Transaction")
            risks.append(_risk(
                "WARNING",
                "Idle-In-Transaction Pressure",
                f"{idle_in_txn} session(s) idle in transaction",
                "Open transactions can block vacuum and retain locks.",
                "Inspect application connection handling and transaction lifecycle.",
                "App Team"
            ))
            recommendations.append(_recommendation(
                "Today",
                "Optimize App Connection Lifecycle",
                "Ensure application correctly closes transactions and doesn't hold them open while idle.",
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
            deductions.append("-10: Active Session Saturation")
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
            deductions.append("-25: Critical TXID Freeze Risk")
            risks.append(_risk(
                "CRITICAL",
                "Transaction ID Freeze Risk",
                f"{freeze_critical} table(s) above critical freeze age",
                "Database availability can be at risk if freeze age is not controlled.",
                "Prioritize vacuum/freeze remediation for critical tables.",
                "DBA"
            ))
            recommendations.append(_recommendation(
                "Urgent",
                "Manual Vacuum Freeze",
                "Run VACUUM FREEZE on critical tables to prevent TXID wraparound.",
                "DBA"
            ))

        elif freeze_warning > 0:
            score -= 10
            deductions.append("-10: Elevated Freeze Age")
            risks.append(_risk(
                "WARNING",
                "Elevated Freeze Age",
                f"{freeze_warning} table(s) above warning threshold",
                "Autovacuum may be falling behind on transaction ID cleanup.",
                "Review freeze-age tables and autovacuum configuration.",
                "DBA"
            ))
            recommendations.append(_recommendation(
                "Scheduled",
                "Tune Autovacuum",
                "Review autovacuum settings and freeze-related parameters.",
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
            deductions.append("-10: Dead Tuple Buildup")
            risks.append(_risk(
                "WARNING",
                "Dead Tuple Buildup",
                f"{high_dead} table(s) with high dead tuples",
                "Bloat and stale visibility can increase IO and query latency.",
                "Review vacuum candidates and autovacuum settings.",
                "DBA"
            ))
            recommendations.append(_recommendation(
                "Today",
                "Address Table Bloat",
                "Investigate why autovacuum is not keeping up with updates/deletes.",
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
            deductions.append("-5: Local Storage (Temp) Spills")
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
            recommendations.append(_recommendation(
                "Today",
                "Tune work_mem or SQL",
                "Increase work_mem for specific sessions or optimize heavy sort/join queries.",
                "DBA"
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

        # Probable Root Cause Assessment
        root_causes_data = _generate_root_causes(
            score, 
            deductions, 
            wait_counts, 
            session_summary, 
            io_summary, 
            freeze_summary, 
            vacuum_summary
        )

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
            "score_explanation": score_explanation,
            "root_causes": root_causes_data,
            "deductions": deductions,
            "connection_utilization": conn_util,
            "connection_status": session_summary.get("utilization_status", "Healthy"),
            "background_processes": waits.get("background_summary", []),
            "active_ratio": active_ratio,
            "top_wait_event_type": wait_metrics.get(
                "top_wait_event_type"
            ),
            "top_wait_event": wait_metrics.get(
                "top_wait_event"
            ),
            "risks": risks[:8],
            "top_risks": risks[:3],
            "recommendations": recommendations[:8],
            "primary_recommendation": recommendations[0] if recommendations else None,
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
            "score_explanation": "Assessment failed to complete.",
            "root_causes": [],
            "deductions": [],
            "background_processes": [],
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

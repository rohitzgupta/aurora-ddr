from utils.db import execute_query


WARNING_THRESHOLD = 200000000
CRITICAL_THRESHOLD = 500000000


def get_status(age_value):

    if age_value >= CRITICAL_THRESHOLD:
        return "CRITICAL"

    if age_value >= WARNING_THRESHOLD:
        return "WARNING"

    return "NORMAL"


def _collect(conn):
    """
    Frozen Transaction ID Analysis
    """

    freeze_age_sql = """
    SELECT

        n.nspname
            AS schema_name,

        c.relname
            AS table_name,

        age(c.relfrozenxid)
            AS freeze_age,

        pg_size_pretty(
            pg_total_relation_size(
                c.oid
            )
        ) AS total_size

    FROM pg_class c

    JOIN pg_namespace n
        ON n.oid = c.relnamespace

    WHERE c.relkind = 'r'

    ORDER BY
        age(c.relfrozenxid) DESC

    LIMIT 50
    """

    database_age_sql = """
    SELECT

        datname,

        age(datfrozenxid)
            AS database_freeze_age

    FROM pg_database

    ORDER BY
        age(datfrozenxid) DESC
    """

    rows = execute_query(
        conn,
        freeze_age_sql
    )

    database_ages = execute_query(
        conn,
        database_age_sql
    )

    critical_tables = 0
    warning_tables = 0

    for row in rows:

        status = get_status(
            row["freeze_age"]
        )

        row["status"] = status

        if status == "CRITICAL":
            critical_tables += 1

        elif status == "WARNING":
            warning_tables += 1

    highest_age = 0

    if rows:

        highest_age = rows[0][
            "freeze_age"
        ]

    summary = {

        "critical_tables":
            critical_tables,

        "warning_tables":
            warning_tables,

        "highest_freeze_age":
            highest_age
    }

    return {

        "summary":
            summary,

        "tables":
            rows,

        "databases":
            database_ages
    }


def collect(conn):

    try:
        return _collect(conn)

    except Exception as exc:
        return {
            "summary": {
                "critical_tables": 0,
                "warning_tables": 0,
                "highest_freeze_age": 0
            },
            "tables": [],
            "databases": [],
            "errors": [
                str(exc)
            ]
        }

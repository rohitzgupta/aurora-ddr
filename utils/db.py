import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str
):
    """
    Create PostgreSQL connection.
    """

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=database,
        user=user,
        password=password,
        connect_timeout=10
    )


def execute_query(conn, sql: str):
    """
    Execute query and return list of dictionaries.
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)

        try:
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []


def execute_scalar(conn, sql: str):

    rows = execute_query(conn, sql)

    if not rows:
        return None

    return list(rows[0].values())[0]


def safe_execute(conn, sql: str):

    try:
        return execute_query(conn, sql)

    except Exception as exc:

        return [{
            "error": str(exc)
        }]
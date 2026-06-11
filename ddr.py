import argparse
import os
import sys
import shutil

from jinja2 import Environment
from jinja2 import FileSystemLoader

from utils.db import get_connection

from collectors import db_info
from collectors import sessions
from collectors import locks
from collectors import sqls
from collectors import findings

from collectors import waits
from collectors import blocking_tree
from collectors import vacuum
from collectors import freeze_age
from collectors import storage
from collectors import parameters


def parse_args():

    parser = argparse.ArgumentParser(
        description="Aurora PostgreSQL Diagnostic Report"
    )

    parser.add_argument(
        "--host",
        required=True
    )

    parser.add_argument(
        "--port",
        default=5432,
        type=int
    )

    parser.add_argument(
        "--database",
        required=True
    )

    parser.add_argument(
        "--user",
        required=True
    )

    parser.add_argument(
        "--password",
        required=True
    )

    return parser.parse_args()


def render_report(context):

    env = Environment(
        loader=FileSystemLoader(
            "templates"
        )
    )

    template = env.get_template(
        "report.html.j2"
    )

    return template.render(
        **context
    )


def save_report(html):

    os.makedirs(
        "output",
        exist_ok=True
    )

    report_file = (
        "output/report.html"
    )

    with open(
        report_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(html)

    return report_file


def main():

    args = parse_args()

    print(
        "\nConnecting to database..."
    )

    try:

        conn = get_connection(
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=args.password
        )

    except Exception as exc:

        print(
            f"Connection failed: {exc}"
        )

        sys.exit(1)

    print(
        "Connection successful."
    )

    try:

        print(
            "Collecting database information..."
        )

        db_info_data = (
            db_info.collect(conn)
        )

        print(
            "Collecting session information..."
        )

        sessions_data = (
            sessions.collect(conn)
        )

        print(
            "Collecting lock information..."
        )

        locks_data = (
            locks.collect(conn)
        )

        print(
            "Collecting wait analysis..."
        )

        waits_data = (
            waits.collect(conn)
        )

        print(
            "Collecting blocking tree..."
        )

        blocking_tree_data = (
            blocking_tree.collect(conn)
        )

        print(
            "Collecting vacuum analysis..."
        )

        vacuum_data = (
            vacuum.collect(conn)
        )

        print(
            "Collecting freeze age analysis..."
        )

        freeze_age_data = (
            freeze_age.collect(conn)
        )

        print(
            "Collecting SQL statistics..."
        )

        sqls_data = (
            sqls.collect(conn)
        )

        print(
            "Collecting storage analysis..."
        )

        storage_data = (
            storage.collect(conn)
        )

        print(
             "Collecting parameter analysis..."
        )

        parameters_data = (
            parameters.collect(conn)
        )

        print(
            "Generating findings..."
        )

        findings_data = (
            findings.collect(
                db_info_data,
                sessions_data,
                locks_data,
                sqls_data,
                waits_data,
                freeze_age_data
            )
        )

        report_context = {

            "db_info":
                db_info_data,

            "sessions":
                sessions_data,

            "locks":
                locks_data,

            "waits":
                waits_data,

            "blocking_tree":
                blocking_tree_data,

            "vacuum":
                vacuum_data,

            "freeze_age":
                freeze_age_data,

            "sqls":
                sqls_data,

            "storage":
                storage_data,

            "parameters":
                parameters_data,

            "findings":
                findings_data
        }

        print(
            "Rendering HTML report..."
        )

        html = render_report(
            report_context
        )

        report_file = save_report(
            html
        )

        shutil.copy(
            "templates/styles.css",
            "output/styles.css"
        )

        print(
            "\nReport generated:"
        )

        print(
            report_file
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()
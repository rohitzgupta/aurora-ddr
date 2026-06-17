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
from collectors import io
from collectors import assessment


def parse_args():

    parser = argparse.ArgumentParser(
        description="Aurora PostgreSQL Health Assessment"
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

        def run_safe(name, collector_mod, *args):
            print(f"Collecting {name}...")
            try:
                data = collector_mod.collect(*args)
                # Ensure transaction is clean for next collector
                conn.rollback()
                return data
            except Exception as e:
                print(f"  Error in {name}: {e}")
                try:
                    conn.rollback()
                except:
                    pass
                return {
                    "errors": [str(e)],
                    "enabled": False,
                    "summary": {},
                    "details": []
                }

        db_info_data = run_safe("database info", db_info, conn)
        sessions_data = run_safe("sessions", sessions, conn)
        locks_data = run_safe("locks", locks, conn)
        waits_data = run_safe("waits", waits, conn)
        blocking_tree_data = run_safe("blocking tree", blocking_tree, conn)
        vacuum_data = run_safe("vacuum", vacuum, conn)
        freeze_age_data = run_safe("freeze age", freeze_age, conn)
        sqls_data = run_safe("SQL statistics", sqls, conn)
        storage_data = run_safe("storage", storage, conn)
        io_data = run_safe("IO pressure", io, conn)
        parameters_data = run_safe("parameters", parameters, conn)

        print("Generating findings...")
        findings_data = findings.collect(
            db_info_data,
            sessions_data,
            locks_data,
            sqls_data,
            waits_data,
            freeze_age_data
        )

        print("Generating health assessment...")
        assessment_data = assessment.collect(
            db_info_data,
            sessions_data,
            locks_data,
            sqls_data,
            waits_data,
            blocking_tree_data,
            vacuum_data,
            freeze_age_data,
            storage_data,
            io_data
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

            "io":
                io_data,

            "parameters":
                parameters_data,

            "findings":
                findings_data,

            "assessment":
                assessment_data
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

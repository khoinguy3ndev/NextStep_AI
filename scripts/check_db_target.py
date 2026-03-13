import os
import sys

from sqlalchemy import text

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from app.db.session import get_standalone_db


def main() -> None:
    db = get_standalone_db()
    try:
        server_info = db.execute(
            text("select inet_server_addr(), inet_server_port(), current_database()")
        ).fetchall()
        tables = db.execute(
            text(
                "select table_name from information_schema.tables where table_schema='public' order by table_name"
            )
        ).fetchall()
        print(server_info)
        print(tables)
    finally:
        db.close()


if __name__ == "__main__":
    main()

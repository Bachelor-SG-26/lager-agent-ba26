import sqlite3

import config
from database.models import create_tables
from database.seed import seed_data


def get_connection():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


class db_connection:
    def __init__(self, commit=False):
        self.commit = commit
        self.conn = None

    def __enter__(self):
        self.conn = get_connection()
        return self.conn, self.conn.cursor()

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None and self.commit:
            self.conn.commit()
        elif exc_type is not None:
            self.conn.rollback()
        self.conn.close()
        return False


def init_db():
    with db_connection(commit=True) as (_, cursor):
        create_tables(cursor)
        seed_data(cursor)

"""Connects to PostgreSQL and runs SQL.

Every INSERT / UPDATE the app runs is printed in the terminal, so you can
show exactly which SQL each click sends to the database.
"""
import re
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

import config


def connect(dbname=None, autocommit=False):
    return psycopg.connect(host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER,
                           password=config.DB_PASSWORD, dbname=dbname or config.DB_NAME,
                           row_factory=dict_row, autocommit=autocommit)


def show(conn, sql, params):
    """Print the SQL with its values filled in."""
    text = psycopg.ClientCursor(conn).mogrify(sql, params)
    text = re.sub(r"'(scrypt|pbkdf2)[^']*'", "'<hashed password>'", text)   # keep the log readable
    print("SQL>", " ".join(text.split()), flush=True)


def query(sql, params=None):
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql, params=None):
    rows = query(sql, params)
    return rows[0] if rows else None


class _Transaction:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        show(self.conn, sql, params)
        cur = self.conn.execute(sql, params)
        return cur.fetchone() if cur.description else None


@contextmanager
def transaction():
    """All statements inside succeed together, or none are saved."""
    with connect() as conn:          # commits at the end, rolls back on any error
        yield _Transaction(conn)


def execute(sql, params=None):
    with transaction() as tx:
        return tx.execute(sql, params)

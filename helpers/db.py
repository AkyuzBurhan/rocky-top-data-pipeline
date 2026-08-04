"""
Database engine factories.

Two very different databases are involved:

1. UTK MySQL/MariaDB (host: mariadb-compx0.oit.utk.edu)
   - Reference source -> read stores/products/new_products.
   - Our team database (bakyuz_bzan545) -> publish final tables here.
   Only reachable on campus or through the UTK VPN, so GitHub Actions cannot
   use it. Credentials come from credentials.json (git-ignored).

2. Local SQLite file (rocky_top.db)
   - The automation engine. No network needed, so the daily GitHub Actions
     job runs the whole pipeline against this file.

create_mysql_utk_engine is a generalized version of the class-provided helper.
"""

import json

import sqlalchemy

from helpers import config


def _load_credentials():
    """Read git-ignored credentials.json. See credentials.example.json."""
    if not config.CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Missing {config.CREDENTIALS_PATH.name}. Copy credentials.example.json "
            "to credentials.json and fill in your UTK username/password/db names."
        )
    with open(config.CREDENTIALS_PATH) as f:
        return json.load(f)


def create_mysql_utk_engine(
    database,
    username,
    password,
    host="mariadb-compx0.oit.utk.edu",
    port=3306,
):
    """Create a SQLAlchemy engine for a UTK MariaDB database (generalized from
    the class-provided helper)."""
    connection_string = sqlalchemy.URL.create(
        "mysql+pymysql",
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
    )
    return sqlalchemy.create_engine(connection_string)


def _mysql_engine(creds, database):
    """Build a UTK MySQL engine, reading host/port from credentials.json when
    present and falling back to the standard UTK MariaDB defaults."""
    return create_mysql_utk_engine(
        database=database,
        username=creds["username"],
        password=creds["password"],
        host=creds.get("host") or "mariadb-compx0.oit.utk.edu",
        port=creds.get("port") or 3306,
    )


def get_source_engine():
    """Engine for the database we READ reference tables from.

    Uses 'source_db' from credentials.json when present (the instructor's DB),
    otherwise falls back to the team DB -- handy when the reference tables
    already live in our own team database (bakyuz_bzan545)."""
    creds = _load_credentials()
    database = (creds.get("source_db")
                or creds.get("team_db")
                or config.TEAM_DB_DEFAULT)
    return _mysql_engine(creds, database)


def get_team_engine():
    """Engine for OUR team database (bakyuz_bzan545): where we publish the
    modeled/analytics tables. The DB name defaults to config.TEAM_DB_DEFAULT,
    so credentials.json only needs username + password (host/port optional)."""
    creds = _load_credentials()
    database = creds.get("team_db") or config.TEAM_DB_DEFAULT
    return _mysql_engine(creds, database)


def get_sqlite_engine():
    """Engine for the local SQLite pipeline database (the automation engine).
    Enables foreign-key enforcement on every connection."""
    engine = sqlalchemy.create_engine(f"sqlite:///{config.SQLITE_PATH}")

    @sqlalchemy.event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine

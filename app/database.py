"""SQLite connection and SQLAlchemy session configuration."""

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = "sqlite:///./certificates.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class shared by all SQLAlchemy models."""


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_database(database_engine=engine) -> None:
    """Create tables and add result columns to older SQLite databases."""
    Base.metadata.create_all(bind=database_engine)

    # create_all does not add columns to a table that already exists. Keep this
    # small migration here so existing jobs and recipients remain available.
    columns = {column["name"] for column in inspect(database_engine).get_columns("recipients")}
    migrations = {
        "generation_status": "VARCHAR(30) NOT NULL DEFAULT 'pending'",
        "pdf_path": "VARCHAR(500)",
        "failure_message": "TEXT",
    }
    with database_engine.begin() as connection:
        for column_name, column_type in migrations.items():
            if column_name not in columns:
                connection.execute(
                    text(f"ALTER TABLE recipients ADD COLUMN {column_name} {column_type}")
                )

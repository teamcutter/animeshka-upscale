from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from src.infrastructure.db.engine import create_db_engine
from src.infrastructure.db.migrate import downgrade_database, upgrade_database
from src.infrastructure.db.models import Base


def test_migrations_match_models(database_url: str) -> None:
    """Fails if a model was changed without `alembic revision --autogenerate`."""
    engine = create_db_engine(database_url)
    upgrade_database(engine)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == []


def test_upgrade_and_downgrade(database_url: str) -> None:
    engine = create_db_engine(database_url)
    upgrade_database(engine)
    assert {"jobs", "files", "metrics"} <= set(inspect(engine).get_table_names())

    downgrade_database(engine)
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()

"""Database migrations using Alembic."""

import os

from alembic.config import Config as AlembicConfig

from alembic import command
from database.database_manager import DatabaseManager
from utils.exceptions import DatabaseException
from utils.system.logger import logger


def run_migrations() -> bool:
    """Run all database migrations using Alembic."""
    try:
        # Load Alembic config from project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ini_path = os.path.join(project_root, "alembic.ini")
        alembic_cfg = AlembicConfig(ini_path)

        # Override the sqlalchemy.url dynamically using our current database path
        from config import DATABASE_PATH

        db_path = (
            DatabaseManager._engine.url if DatabaseManager._engine else DATABASE_PATH
        )
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

        logger.info("Running Alembic migrations on current database connection...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully")
        return True
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise DatabaseException(f"Migration failed: {str(e)}") from e

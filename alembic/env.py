import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Engine

from alembic import context

# Ensure the project root directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# add your model's MetaData object here
# for 'autogenerate' support
from sqlmodel import SQLModel

target_metadata = SQLModel.metadata


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in [
        "sqlite_sequence",
        "test_table",
        "customer_payments",
    ]:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=False,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Check if a connection/engine was passed in config attributes
    connectable = config.attributes.get("connection", None)

    if connectable is None:
        # Fallback to loading/initializing DatabaseManager or config
        from database.database_manager import DatabaseManager

        if DatabaseManager._engine is not None:
            connectable = DatabaseManager._engine
        else:
            connectable = engine_from_config(
                config.get_section(config.config_ini_section, {}),
                prefix="sqlalchemy.",
                poolclass=pool.NullPool,
            )

    if isinstance(connectable, Engine):
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_object=include_object,
                compare_type=False,
            )

            with context.begin_transaction():
                context.run_migrations()
    else:
        # If it is an active Connection object passed directly
        context.configure(
            connection=connectable,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

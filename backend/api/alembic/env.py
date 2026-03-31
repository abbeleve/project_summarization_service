# backend/api/alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.db_service.database import Base  # ← ваша базовая модель
import os

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Устанавливаем target_metadata для autogenerate
target_metadata = Base.metadata

def get_url():
    """
    Получает URL подключения к PostgreSQL.

    Для локального запуска (venv):
        export DB_HOST=localhost
        export DB_USER=postgres_user
        export DB_PASSWORD=your_password
        export DB_NAME=postgres
        export DB_PORT=5430  # ← внешний порт из docker-compose

    Для Docker (по умолчанию):
        DB_HOST=postgres
        DB_PORT=5432
    """
    return (
        f"postgresql://"
        f"{os.getenv('POSTGRES_USER', 'postgres_user')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'postgres_password')}@"
        f"{os.getenv('DB_HOST', 'localhost')}:"
        f"{os.getenv('DB_PORT', '5430')}/"  # ← слеш перед именем БД
        f"{os.getenv('POSTGRES_DB', 'postgres')}"
    )

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
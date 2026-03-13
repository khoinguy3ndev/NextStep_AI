import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# --- PHẦN SỬA ĐỔI 1: Thêm đường dẫn để Python tìm thấy thư mục 'app' ---
sys.path.append(os.getcwd())

# --- PHẦN SỬA ĐỔI 2: Import Base từ file gom Model của bạn ---
from app.db.base import Base #

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- PHẦN SỬA ĐỔI 3: Gán MetaData để hỗ trợ autogenerate ---
target_metadata = Base.metadata #

# (Giữ nguyên các phần còn lại bên dưới của bạn)
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
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
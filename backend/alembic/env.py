import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import pool
from logging.config import fileConfig
import os
import asyncio
from dotenv import load_dotenv

from app.models import Base  # update this path if needed

# Load env variables
load_dotenv()

# Set config
config = context.config
fileConfig(config.config_file_name)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing")

config.set_main_option("sqlalchemy.url", DATABASE_URL)
target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", DATABASE_URL)
target_metadata = Base.metadata

from app.models import Base  # adjust path if needed

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", DATABASE_URL)

def run_migrations_online():
    connectable = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
        future=True,
    )

    async def do_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(
                lambda conn: context.configure(connection=conn, target_metadata=target_metadata)
            )
            async with context.begin_transaction():
                context.run_migrations()

    asyncio.run(do_migrations())

run_migrations_online()
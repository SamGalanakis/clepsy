from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import AsyncGenerator, Literal

import aiosqlite

from clepsy import utils
from clepsy.config import config
from clepsy.db import adapters, converters


TransactionTypes = Literal["DEFERRED", "IMMEDIATE", "EXCLUSIVE"]


@asynccontextmanager
async def get_db_connection(
    db_path: Path = config.db_path,
    start_transaction: bool = False,
    include_uuid_func: bool = True,
    commit_on_exit: bool = True,
    parse_decltypes: bool = True,
    busy_timeout: int = 5000,
    transaction_type: TransactionTypes = "IMMEDIATE",
    pragma_synchronous: str = "NORMAL",
    cache_size: int = 2000,
) -> AsyncGenerator[aiosqlite.Connection, None]:
    connection_kwargs = {}

    if parse_decltypes:
        connection_kwargs["detect_types"] = sqlite3.PARSE_DECLTYPES

    conn = await aiosqlite.connect(db_path, **connection_kwargs)
    try:
        if include_uuid_func:
            await conn.create_function(
                "generate_uuid", 0, utils.generate_uuid, deterministic=False
            )
        conn.row_factory = aiosqlite.Row
        pragma_string = f"""
        PRAGMA cache_size={cache_size};
        PRAGMA synchronous={pragma_synchronous};
        PRAGMA busy_timeout={busy_timeout};
        PRAGMA foreign_keys=true;
        PRAGMA temp_store=MEMORY;
        """
        await conn.executescript(pragma_string)
        if start_transaction:
            await conn.execute(f"BEGIN {transaction_type} TRANSACTION")

        yield conn

        if commit_on_exit:
            await conn.commit()
    except Exception:
        if start_transaction:
            await conn.rollback()
        raise
    finally:
        await conn.close()


async def db_setup():
    async with get_db_connection(start_transaction=False) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")

    aiosqlite.register_adapter(datetime, adapters.adapt_timestamp)

    aiosqlite.register_converter("DATETIME", converters.convert_date)

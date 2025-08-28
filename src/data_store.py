import asyncio
import os
import pathlib as p
from contextlib import asynccontextmanager
from typing import Dict, List

import aiosqlite as sql


HSS_DB_PATH = p.Path("db/hss_data.db")

_connection_pool_cache: Dict[p.Path, "DBConnectionPool"] = {}


class DBConnectionPool:
    def __init__(
        self,
        db_path: p.Path,
        pool_size: int = 5,
        db_busy_timeout_ms: int = 5000,
    ) -> None:
        assert pool_size > 0
        assert db_busy_timeout_ms >= 0

        assert _connection_pool_cache.get(db_path) is None

        self.db_path = db_path
        self.pool_size = pool_size
        self.db_busy_timeout_ms = db_busy_timeout_ms

        self.write_lock = asyncio.Lock()
        self.pool: List[sql.Connection]

    async def create_pool(self):
        self.pool = []

        for _ in range(self.pool_size):
            conn = await sql.connect(str(self.db_path), timeout=30)

            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute(f"PRAGMA busy_timeout={self.db_busy_timeout_ms}")

            self.pool.append(conn)

    async def close_pool(self):
        for conn in self.pool:
            await conn.close()

    @asynccontextmanager
    async def get_connection(self):
        # TODO: maybe add a wait queue so this doesn't fail an assertion if the connection pool is empty
        assert self.pool is not None and len(self.pool) != 0

        conn = self.pool.pop()

        try:
            yield conn
        finally:
            self.pool.append(conn)

    @asynccontextmanager
    async def get_write_connection(self):
        async with self.write_lock, self.get_connection() as conn:
            yield conn

    @staticmethod
    async def get_connection_pool(
        db_path: p.Path, pool_size: int = 5, db_busy_timeout_ms: int = 5000
    ) -> "DBConnectionPool":

        conn_pool = _connection_pool_cache.get(db_path)

        if conn_pool is not None:
            return conn_pool

        conn_pool = DBConnectionPool(db_path, pool_size, db_busy_timeout_ms)

        # TODO: perhaps do the same thing that was done with HSSDatabase to allow `await` in a constructor type function
        await conn_pool.create_pool()

        _connection_pool_cache[db_path] = conn_pool

        return conn_pool


class HSSDatabase(object):
    db_path: p.Path
    conn_pool: DBConnectionPool

    @classmethod
    async def new(
        cls,
        db_path: os.PathLike = HSS_DB_PATH,
        pool_size: int = 5,
        db_busy_timeout_ms: int = 5000,
    ) -> "HSSDatabase":
        self = cls()
        self.db_path = p.Path(db_path)

        print(db_path)
        self.conn_pool = await DBConnectionPool.get_connection_pool(
            self.db_path, pool_size, db_busy_timeout_ms
        )

        await self._create_tables()

        return self

    async def __aenter__(self):
        return

    async def __aexit__(self, exception_type, exception_value, exception_traceback):
        await self.close()

    async def _create_modded_subs_table(self, conn: sql.Connection):
        table_query = """
        CREATE TABLE IF NOT EXISTS modded_subs (
            id INTEGER PRIMARY KEY,
            name CHAR(22) NOT NULL UNIQUE COLLATE NOCASE,
            description TEXT,
            moderators TEXT NOT NULL,
            permissions TEXT NOT NULL,
            sub_count INTEGER NOT NULL,
            is_nsfw BOOL NOT NULL,
            sub_id CHAR(5) NOT NULL,
            config TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        await conn.execute(table_query)
        await conn.commit()

        index_query = """
        CREATE INDEX IF NOT EXISTS idx_modded_subs_name ON modded_subs(name)
        """

        await conn.execute(index_query)
        await conn.commit()

    async def _create_blacklist_table(self, conn: sql.Connection):
        table_query = """
        CREATE TABLE blacklist (
            id INTEGER PRIMARY KEY,
            name CHAR(22) NOT NULL UNIQUE COLLATE NOCASE,
            reason TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        await conn.execute(table_query)
        await conn.commit()

        index_query = """
        CREATE INDEX IF NOT EXISTS idx_blacklist_name ON blacklist(name)
        """

        await conn.execute(index_query)
        await conn.commit()

    async def _create_whitelist_table(self, conn: sql.Connection):
        table_query = """
        CREATE TABLE whitelist (
            id INTEGER PRIMARY KEY,
            name CHAR(22) NOT NULL UNIQUE COLLATE NOCASE,
            reason TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        await conn.execute(table_query)
        await conn.commit()

        index_query = """
        CREATE INDEX IF NOT EXISTS idx_whitelist_name ON whitelist(name)
        """

        await conn.execute(index_query)
        await conn.commit()

    async def _create_banned_users_table(self, conn: sql.Connection):
        table_query = """
        CREATE TABLE banned_users (
            id INTEGER PRIMARY KEY,
            name CHAR(22) NOT NULL UNIQUE COLLATE NOCASE,
            reason TEXT NOT NULL,
            duration INTEGER,
            message TEXT,
            mod_scope CHAR(22),
            sub_scope CHAR(22),
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        await conn.execute(table_query)
        await conn.commit()

        index_query = """
        CREATE INDEX idx_banned_users_name ON banned_users(name)
        """

        await conn.execute(index_query)
        await conn.commit()

    async def _create_tables(self):
        async with self.conn_pool.get_write_connection() as conn:
            await self._create_blacklist_table(conn)
            await self._create_whitelist_table(conn)
            await self._create_modded_subs_table(conn)
            await self._create_banned_users_table(conn)

    async def close(self):
        await self.conn_pool.close_pool()

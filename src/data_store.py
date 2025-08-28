import asyncio
import os
import pathlib as p
from contextlib import asynccontextmanager
from typing import Dict, List

import aiosqlite as sql


HSS_DB_PATH = p.Path("db/hss_data.db")

_connection_pool_cache: Dict[p.Path, "DBConnectionPool"] = {}


class DBConnectionPool:
    db_path: p.Path
    pool_size: int
    db_busy_timeout_ms: int

    semaphore: asyncio.BoundedSemaphore

    write_lock: asyncio.Lock
    pool: List[sql.Connection]
    pool_closed: bool

    @classmethod
    async def new(
        cls,
        db_path: p.Path,
        pool_size: int = 5,
        db_busy_timeout_ms: int = 5000,
    ) -> "DBConnectionPool":
        assert pool_size > 0
        assert db_busy_timeout_ms >= 0

        self = _connection_pool_cache.get(db_path)

        if (
            self is not None
            and self.pool_size == pool_size
            and self.db_busy_timeout_ms == db_busy_timeout_ms
        ):
            return self

        self = cls()

        self.db_path = db_path
        self.pool_size = pool_size
        self.db_busy_timeout_ms = db_busy_timeout_ms
        self.semaphore = asyncio.BoundedSemaphore(self.pool_size)

        self.write_lock = asyncio.Lock()
        self.pool_closed = False
        await self.create_pool()

        return self

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
    async def get_connection(self, timeout_secs: "float|None" = None):
        """
        Raises:
            asyncio.TimeoutError - if `timeout_secs` is not None and it timed out
        """
        assert self.pool is not None

        await asyncio.wait_for(self.semaphore.acquire(), timeout=timeout_secs)

        conn = self.pool.pop()

        try:
            yield conn
        finally:
            self.pool.append(conn)
            self.semaphore.release()

    @asynccontextmanager
    async def get_write_connection(self):
        async with self.write_lock, self.get_connection() as conn:
            yield conn


class HSSDatabase:
    db_path: p.Path
    _conn_pool: DBConnectionPool

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
        self._conn_pool = await DBConnectionPool.new(
            self.db_path, pool_size, db_busy_timeout_ms
        )

        await self._create_tables()

        return self

    async def __aenter__(self):
        return

    async def __aexit__(self, exception_type, exception_value, exception_traceback):
        await self.close()

    async def _create_subs_table(self, conn: sql.Connection):
        table_query = """
        CREATE TABLE IF NOT EXISTS subs (
            id INTEGER PRIMARY KEY,
            name CHAR(22) NOT NULL UNIQUE COLLATE NOCASE,
            is_mod BOOL NOT NULL,
            description TEXT,
            moderators TEXT NOT NULL,
            permissions TEXT NOT NULL,
            sub_count INTEGER NOT NULL,
            is_nsfw BOOL NOT NULL,
            sub_id CHAR(5) NOT NULL UNIQUE,
            config TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        await conn.execute(table_query)
        await conn.commit()

        index_query = """
        CREATE INDEX IF NOT EXISTS idx_subs_name_is_mod ON subs(name, is_mod)
        """

        await conn.execute(index_query)
        await conn.commit()

    async def _create_bans_table(self, conn: sql.Connection):
        table_query = """
        CREATE TABLE IF NOT EXISTS bans (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES banned_users(id),
            sub_id INTEGER NOT NULL REFERENCES subs(id),
            efective_duration INTEGER,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        await conn.execute(table_query)
        await conn.commit()

        index_query = """
        CREATE INDEX IF NOT EXISTS idx_bans_user_id ON bans(user_id)
        """

        await conn.execute(index_query)
        await conn.commit()

    async def _create_banned_users_table(self, conn: sql.Connection):
        table_query = """
        CREATE TABLE IF NOT EXISTS banned_users (
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
        CREATE INDEX IF NOT EXISTS idx_banned_users_name ON banned_users(name)
        """

        await conn.execute(index_query)
        await conn.commit()

    async def _create_blacklist_table(self, conn: sql.Connection):
        table_query = """
        CREATE TABLE IF NOT EXISTS blacklist (
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
        CREATE TABLE IF NOT EXISTS whitelist (
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

    async def _create_tables(self):
        async with self._conn_pool.get_write_connection() as conn:
            await self._create_blacklist_table(conn)
            await self._create_whitelist_table(conn)
            await self._create_subs_table(conn)
            await self._create_banned_users_table(conn)
            await self._create_bans_table(conn)

    async def close(self):
        await self._conn_pool.close_pool()

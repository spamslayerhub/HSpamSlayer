from datetime import datetime
import unittest
import aiosqlite as sql
from pathlib import Path as p

import src.data_store as data_store


# no need to test whitelist here since it uses the same class as blacklist
class TestBlacklist(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = await data_store.HSSDataStore.new(p(":memory:"))
        self.addAsyncCleanup(self.store.close)

    async def test_add(self):

        await self.store.blacklist.add("test", None)

        with self.assertRaises(sql.IntegrityError):
            await self.store.blacklist.add("test", None)

    async def test_contains(self):
        await self.store.blacklist.add("test_contains", None)

        self.assertTrue(await self.store.blacklist.contains("test_contains"))
        self.assertFalse(await self.store.blacklist.contains("test_contains1"))

    async def test_get(self):
        await self.store.blacklist.add("test_get", "test")

        entry = await self.store.blacklist.get("test_get")

        self.assertIsNotNone(entry)
        assert entry is not None

        self.assertEqual(entry.name, "test_get")
        self.assertEqual(entry.reason, "test")
        self.assertIsInstance(entry.added_at, datetime)

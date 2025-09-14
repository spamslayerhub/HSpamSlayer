from tortoise.contrib import test
from src.datastore.models import Sub
from src.datastore.custom_fields import Permission


class TestSub(test.IsolatedTestCase):
    async def test_create_sub(self):
        s = Sub(
            name="test",
            is_mod=True,
            description="test_sub",
            permissions=Permission.all(),
            sub_count=10,
            is_nsfw=False,
            is_banned=False,
            sub_id="test1",
            config="",
        )
        await s.save()

        s1 = await Sub.get(name="test")
        self.assertEqual(s, s1)

    @test.expectedFailure
    async def test_get_sub_bad(self):
        await Sub.get(name="test")

    async def test_update_sub(self):
        s_og = Sub(
            name="test",
            is_mod=True,
            description="test_sub",
            permissions=Permission.all(),
            sub_count=10,
            is_nsfw=False,
            is_banned=False,
            sub_id="test1",
            config="",
        )

        await s_og.save()

        s_new = await Sub.get(name="test")
        s_new.is_banned = True
        await s_new.save()

        s_current = await Sub.get(name="test")

        self.assertNotEqual(s_og.is_banned, s_current.is_banned)
        self.assertEqual(s_new.is_banned, s_current.is_banned)

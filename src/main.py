import asyncio
import data_store


async def main() -> int:
    db = await data_store.HSSDatabase.new()
    await db.close()

    print("Hello, World!")
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))

import asyncio
import data_store


async def main() -> int:
    store = await data_store.HSSDataStore.new()
    await store.close()

    print("Hello, World!")
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))

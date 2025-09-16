import asyncio


async def main() -> int:
    print("Hello, World!")
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))

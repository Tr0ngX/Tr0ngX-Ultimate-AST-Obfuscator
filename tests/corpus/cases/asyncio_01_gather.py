import asyncio


async def work(name, delay, result):
    await asyncio.sleep(delay)
    return f"{name}={result}"


async def main():
    results = await asyncio.gather(
        work("a", 0.01, 1),
        work("b", 0.02, 2),
        work("c", 0.005, 3),
    )
    print(results)


asyncio.run(main())

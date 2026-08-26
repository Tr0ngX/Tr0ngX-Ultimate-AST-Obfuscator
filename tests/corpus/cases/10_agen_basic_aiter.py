import asyncio


async def countdown(n):
    for i in range(n, -1, -1):
        await asyncio.sleep(0.001)
        yield i


async def squares(agen):
    async for v in agen:
        yield v * v


async def main():
    out = [v async for v in squares(countdown(5))]
    print(out)
    g = countdown(3)
    first = await g.__anext__()
    print(first)
    await g.aclose()
    try:
        await g.__anext__()
    except StopAsyncIteration:
        print("closed cleanly")


asyncio.run(main())

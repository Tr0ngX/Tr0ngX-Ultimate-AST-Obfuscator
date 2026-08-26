import asyncio


async def acc():
    total = 0
    while True:
        x = yield total
        if x is None:
            break
        total += x
    return total


async def main():
    g = acc()
    await g.asend(None)
    print(await g.asend(5))
    print(await g.asend(10))
    try:
        await g.asend(None)
    except StopAsyncIteration as e:
        print("stop:", e.value)


asyncio.run(main())

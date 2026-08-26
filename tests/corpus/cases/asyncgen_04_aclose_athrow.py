import asyncio

events = []


async def tracked():
    try:
        for i in range(10):
            yield i
            events.append(("yielded", i))
    finally:
        events.append("closed")


async def main():
    g = tracked()
    print(await g.__anext__())
    print(await g.__anext__())
    await g.aclose()
    print(events)

    g2 = tracked()
    await g2.__anext__()
    try:
        await g2.athrow(ValueError("boom"))
    except ValueError as e:
        print("caught", type(e).__name__, str(e))
    print(events[-1])


asyncio.run(main())

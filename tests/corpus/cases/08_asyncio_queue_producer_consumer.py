import asyncio


async def producer(q, items):
    for it in items:
        await q.put(it)
    await q.put(None)


async def consumer(q, out):
    while True:
        item = await q.get()
        if item is None:
            await q.put(None)
            break
        out.append(item * 2)
        q.task_done()


async def main():
    q = asyncio.Queue(maxsize=3)
    out = []
    await asyncio.gather(producer(q, range(8)), consumer(q, out))
    print(out)
    print(q.empty())


asyncio.run(main())

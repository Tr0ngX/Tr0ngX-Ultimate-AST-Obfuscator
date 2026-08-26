import asyncio


async def agen(n):
    for i in range(n):
        await asyncio.sleep(0)
        yield i * i


async def main():
    out = [x async for x in agen(6)]
    print(out)
    total = 0
    async for v in agen(4):
        total += v
    print(total)


asyncio.run(main())

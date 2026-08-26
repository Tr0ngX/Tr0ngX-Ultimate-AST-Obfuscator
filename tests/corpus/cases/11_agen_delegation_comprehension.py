import asyncio


async def letters(text):
    for ch in text:
        await asyncio.sleep(0)
        yield ch


async def numbered(agen, start):
    n = start
    async for ch in agen:
        yield (n, ch)
        n += 1


async def main():
    pairs = [(n, c) async for n, c in numbered(letters("abc"), 10)]
    print(pairs)
    merged = [ch async for ch in letters("xy")]
    merged += [ch async for ch in letters("zw!")]
    print("".join(merged))


asyncio.run(main())

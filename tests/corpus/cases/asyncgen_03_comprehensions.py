import asyncio


async def letters(seq):
    for item in seq:
        await asyncio.sleep(0)
        yield item


async def main():
    upper = [ch.upper() async for ch in letters("abcde")]
    pairs = {i: ch for i, ch in zip(range(3), [c async for c in letters("xyz")])}
    joined = "".join([w async for w in letters(["ab", "cd"])])
    total = sum(1 async for _ in letters(range(7)))
    print(upper)
    print(pairs)
    print(joined, total)


asyncio.run(main())

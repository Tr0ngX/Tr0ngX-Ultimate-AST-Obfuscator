import asyncio


async def accumulator():
    total = 0
    count = 0
    err = False
    try:
        while True:
            payload = ("err", total) if err else ("ok", total)
            v = yield payload
            err = False
            if v == "STOP":
                break
            if isinstance(v, RuntimeError):
                err = True
                continue
            total += v
            count += 1
    finally:
        print(f"total={total} count={count}")


async def main():
    g = accumulator()
    print(await g.asend(None))
    print(await g.asend(5))
    print(await g.asend(7))
    print(await g.athrow(RuntimeError()))
    print(await g.asend(1))
    await g.aclose()


asyncio.run(main())

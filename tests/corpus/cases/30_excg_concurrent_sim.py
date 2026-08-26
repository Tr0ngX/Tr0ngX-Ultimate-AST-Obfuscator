import asyncio


class JobErr(Exception):
    pass


async def job(name, fail_with=None):
    await asyncio.sleep(0.001)
    if fail_with is not None:
        raise fail_with
    return name


async def fanout():
    outcomes = await asyncio.gather(
        job("j1"),
        job("j2", JobErr("e2")),
        job("j3"),
        job("j4", JobErr("e4")),
        return_exceptions=True,
    )
    errs = [o for o in outcomes if isinstance(o, Exception)]
    oks = [o for o in outcomes if not isinstance(o, Exception)]
    print(oks)
    if errs:
        raise ExceptionGroup("fanout-errors", errs)


try:
    asyncio.run(fanout())
except ExceptionGroup as eg:
    print(sorted(str(e) for e in eg.exceptions))

import asyncio
from contextlib import ExitStack, AsyncExitStack, contextmanager, asynccontextmanager

order = []


@contextmanager
def cm(tag):
    order.append("in:" + tag)
    try:
        yield tag
    finally:
        order.append("out:" + tag)


@asynccontextmanager
async def acm(tag):
    order.append("ain:" + tag)
    try:
        yield tag
    finally:
        order.append("aout:" + tag)


with ExitStack() as st:
    st.enter_context(cm("one"))
    st.callback(order.append, "cb-one")
    st.enter_context(cm("two"))


async def main():
    async with AsyncExitStack() as st:
        await st.enter_async_context(acm("net"))
        st.push_async_callback(order.append, "acb-net")
        await st.enter_async_context(acm("disk"))
    print("\n".join(order))


asyncio.run(main())

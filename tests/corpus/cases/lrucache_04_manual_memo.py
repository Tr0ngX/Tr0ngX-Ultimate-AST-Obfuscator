import functools


@functools.cache
def ways(n):
    if n <= 1:
        return 1
    return ways(n - 1) + ways(n - 2)


print(ways(20))
print(ways.cache_info().misses)


def memoize_user(fn):
    store = {}

    def wrapped(*args):
        if args not in store:
            store[args] = fn(*args)
        return store[args]

    wrapped.clear_store = store.clear
    return wrapped


@memoize_user
def sq(x):
    sq.ticks = getattr(sq, "ticks", 0) + 1
    return x * x


print(sq(4), sq(4), sq(5))
print(sq.ticks)
sq.clear_store()
print(sq.ticks)

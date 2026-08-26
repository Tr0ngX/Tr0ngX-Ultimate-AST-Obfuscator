import functools


def traced(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        wrapper.calls += 1
        return result

    wrapper.calls = 0
    return wrapper


@traced
def add(a, b):
    """Add two numbers."""
    return a + b


print(add(1, 2), add(3, 4))
print(add.__name__, add.__doc__, add.__wrapped__(10, 5))
print(add.calls)
print(traced(lambda x: x)(7))

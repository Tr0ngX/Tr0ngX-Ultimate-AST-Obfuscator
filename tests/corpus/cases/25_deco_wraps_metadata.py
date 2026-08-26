import functools


def loud(func):
    @functools.wraps(func)
    def wrapper(*a, **k):
        print(f"call:{func.__name__}")
        return func(*a, **k)
    return wrapper


def bare(func):
    def wrapper(*a, **k):
        return func(*a, **k)
    return wrapper


@loud
def sample(x, y=1):
    """sample docs"""
    return x + y


@bare
def other(x):
    return x - 1


print(sample(2, y=3))
print(sample.__name__, sample.__doc__)
print(other.__name__)
print(sample.__wrapped__(10, y=5))
print(functools.reduce(lambda a, b: a + b, [1, 2, 3, 4]))
print(functools.partial(sample, 1)(y=2))

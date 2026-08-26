import functools


class CountCalls:
    def __init__(self, fn):
        functools.update_wrapper(self, fn)
        self.fn = fn
        self.count = 0

    def __call__(self, *args, **kwargs):
        self.count += 1
        return self.fn(*args, **kwargs)


@CountCalls
def square(x):
    return x * x


print(square(3), square(4), square(5))
print(square.count, square.__name__)


def register(store):
    def deco(cls):
        store[cls.__name__] = cls
        return cls

    return deco


REG = {}


@register(REG)
class Alpha:
    tag = "A"


@register(REG)
class Beta:
    tag = "B"


keys = sorted(REG)
print(keys)
print([REG[k].tag for k in keys])

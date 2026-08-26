import functools


def repeat(times):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return [fn(*args, **kwargs) for _ in range(times)]

        return wrapper

    return deco


@repeat(times=3)
def ping(msg):
    return msg.upper()


print(ping("hey"))


def validate(*types):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args):
            for a, t in zip(args, types):
                if not isinstance(a, t):
                    raise TypeError("arg mismatch")
            return fn(*args)

        return wrapper

    return deco


@validate(int, int)
def sub(a, b):
    return a - b


print(sub(9, 4))
try:
    sub("a", 1)
except TypeError as e:
    print("TypeError:", e)

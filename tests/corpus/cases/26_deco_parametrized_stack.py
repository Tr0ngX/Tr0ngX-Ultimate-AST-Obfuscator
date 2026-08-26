import functools

CALLS = []


def trace(label):
    def deco(func):
        @functools.wraps(func)
        def inner(*a, **k):
            CALLS.append(f">{label}:{func.__name__}")
            try:
                return func(*a, **k)
            finally:
                CALLS.append(f"<{label}:{func.__name__}")
        return inner
    return deco


def retry(times):
    def deco(func):
        @functools.wraps(func)
        def inner(*a, **k):
            last = None
            for attempt in range(times):
                try:
                    return func(*a, **k)
                except ValueError as e:
                    last = e
                    CALLS.append(f"retry{attempt}")
            raise last
        return inner
    return deco


flaky_state = {"n": 0}


@trace("outer")
@retry(3)
@trace("inner")
def unstable():
    flaky_state["n"] += 1
    if flaky_state["n"] < 3:
        raise ValueError("not yet")
    return "stable"


print(unstable())
print(CALLS)

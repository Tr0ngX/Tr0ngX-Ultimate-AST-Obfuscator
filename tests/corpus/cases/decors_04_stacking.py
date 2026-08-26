import functools


def bold(fn):
    @functools.wraps(fn)
    def w(*a, **k):
        return "<b>" + fn(*a, **k) + "</b>"

    return w


def italic(fn):
    @functools.wraps(fn)
    def w(*a, **k):
        return "<i>" + fn(*a, **k) + "</i>"

    return w


def suffix(mark):
    def deco(fn):
        @functools.wraps(fn)
        def w(*a, **k):
            return fn(*a, **k) + mark

        return w

    return deco


@bold
@italic
@suffix("!")
def greet(name):
    return f"hi {name}"


print(greet("sam"))
print(greet.__wrapped__("kim"))

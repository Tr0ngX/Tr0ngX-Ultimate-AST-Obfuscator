def inner():
    yield 1
    yield 2
    return "inner-done"


def middle():
    got = yield from inner()
    yield got.upper()
    return "mid"


def outer():
    res = yield from middle()
    yield "outer:" + res


vals = []
o = outer()
try:
    while True:
        vals.append(next(o))
except StopIteration:
    pass
print(vals)

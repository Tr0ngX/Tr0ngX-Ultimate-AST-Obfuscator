def echo():
    acc = []
    while True:
        try:
            x = yield "ready"
        except ValueError as e:
            acc.append(("err", str(e)))
            continue
        if x is None:
            break
        acc.append(x)
    return tuple(acc)


g = echo()
print(next(g))
print(g.send("a"))
print(g.throw(ValueError("boom")))
try:
    g.send(None)
except StopIteration as stop:
    print(stop.value)


def closer():
    try:
        yield 1
        yield 2
    finally:
        print("cleanup ran")


c = closer()
print(next(c))
c.close()
try:
    next(c)
except StopIteration:
    print("closed-exhausted")
print(list(closer()))

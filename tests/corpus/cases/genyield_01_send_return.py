def echo():
    total = 0
    while True:
        n = yield total
        if n is None:
            break
        total += n
    return total


g = echo()
print(next(g))
print(g.send(5))
print(g.send(7))
try:
    g.send(None)
except StopIteration as e:
    print("returned:", e.value)

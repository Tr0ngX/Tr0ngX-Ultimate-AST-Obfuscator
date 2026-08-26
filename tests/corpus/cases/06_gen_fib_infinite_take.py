import itertools


def fib():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


print(list(itertools.islice(fib(), 15)))
print(list(itertools.takewhile(lambda x: x < 100, fib())))


def window(seq, k):
    it = iter(seq)
    win = []
    for v in it:
        win.append(v)
        if len(win) == k:
            yield tuple(win)
            win.pop(0)


print(list(window(fib(), 3))[:5])


def indexed():
    for i, f in enumerate(fib()):
        if i > 8:
            break
        yield (i, f)


print(dict(indexed()))

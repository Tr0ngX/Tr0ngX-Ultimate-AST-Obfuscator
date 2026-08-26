def source(n):
    total = 0
    for i in range(n):
        yield i
        total += i
    return total


def wrapper(n):
    total = yield from source(n)
    yield ("sum", total)


def doubler(it):
    for v in it:
        yield v * 2


def lvl3(n):
    r = yield from wrapper(n)
    yield ("lvl3-saw", r)


print(list(doubler(source(5))))
print(list(wrapper(5)))
print(list(lvl3(4)))


def tree(depth):
    if depth == 0:
        yield "leaf"
        return
    yield f"node{depth}"
    sub = yield from tree(depth - 1)
    yield f"back{sub}"


print(list(tree(3)))

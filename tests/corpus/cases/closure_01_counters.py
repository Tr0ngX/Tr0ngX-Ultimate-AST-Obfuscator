def make_counter(start=0, step=1):
    count = start

    def inc():
        nonlocal count
        count += step
        return count

    def reset():
        nonlocal count
        count = start
        return count

    inc.reset = reset
    return inc


a = make_counter()
b = make_counter(10, 5)
print([a() for _ in range(3)])
print([b() for _ in range(2)])
print(a.reset())
print(a())
print(len(a.__closure__), len(b.__closure__))

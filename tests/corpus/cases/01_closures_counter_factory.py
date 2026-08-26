def make_counter(start=0, step=1):
    count = start
    calls = 0

    def inc():
        nonlocal count, calls
        count += step
        calls += 1
        return count

    def stats():
        return (count, calls)

    inc.stats = stats
    return inc


a = make_counter()
b = make_counter(100, -7)
outs = []
for _ in range(3):
    outs.append(a())
b()
b()
outs.append(a.stats())
outs.append(b.stats())
c1 = make_counter(5)
c2 = c1
c1()
c1()
outs.append(c2())
print(outs)

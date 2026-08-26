lambdas_broken = [lambda: i for i in range(3)]
lambdas_fixed = [lambda i=i: i * 10 for i in range(3)]
print([f() for f in lambdas_broken])
print([f() for f in lambdas_fixed])


def outer():
    fns = []
    for n in ("x", "y", "z"):
        def get(n=n):
            return n.upper()
        fns.append(get)
    return [f() for f in fns]


print(outer())


def make_adder(base):
    def add(v):
        return v + base
    return add


adders = [make_adder(k) for k in range(1, 4)]
print([a(100) for a in adders])
print([adders[0](v) for v in (0, 10)])

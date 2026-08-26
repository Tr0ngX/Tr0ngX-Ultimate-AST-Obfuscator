def build():
    cache = {}

    def fib(n):
        if n in cache:
            return cache[n]
        value = n if n < 2 else fib(n - 1) + fib(n - 2)
        cache[n] = value
        return value

    return fib


f = build()
print([f(i) for i in range(12)])
cell = f.__closure__[0].cell_contents
print(sorted(cell.items()))
print(cell[11])

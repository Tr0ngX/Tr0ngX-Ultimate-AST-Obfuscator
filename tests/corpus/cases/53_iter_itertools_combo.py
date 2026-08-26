import itertools


def collatz(n):
    while n != 1:
        yield n
        n = n // 2 if n % 2 == 0 else 3 * n + 1
    yield 1


seq = list(collatz(6))
print(seq)
grouped = [list(g) for _, g in itertools.groupby(seq, key=lambda x: x % 2)]
print(grouped)
zipped = list(itertools.zip_longest(collatz(3), collatz(7), fillvalue=-1))
print(zipped[:4])
chained = list(itertools.chain.from_iterable([collatz(2), collatz(4)]))
print(chained)
cycled = list(itertools.islice(itertools.cycle([1, 2]), 7))
print(cycled)
print(sum(itertools.starmap(lambda a, b: a * b, zip(collatz(4), collatz(4)))))

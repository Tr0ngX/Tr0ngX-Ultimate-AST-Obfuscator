nums = range(1, 21)
evens = (n for n in nums if n % 2 == 0)
squared = (n * n for n in evens)
limited = (n for n in squared if n < 100)
print(list(limited))


def chunker(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


print(list(chunker("abcdefghij", 4)))
print(list(chunker(list(range(7)), 3)))

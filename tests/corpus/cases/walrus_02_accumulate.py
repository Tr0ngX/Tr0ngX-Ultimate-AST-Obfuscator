values = [5, 3, 8, 2, 9]
tot = 0
running = [tot := tot + v for v in values]
print(running)

matrix = [[1, 2, 3], [4, 5], []]
counts = [n for row in matrix if (n := len(row))]
print(counts)

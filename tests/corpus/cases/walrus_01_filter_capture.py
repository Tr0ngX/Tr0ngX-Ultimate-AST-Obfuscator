data = [3, -1, 8, -7, 12, 0, -4]
kept = [y for x in data if (y := abs(x)) > 3]
print(kept)

words = ["apple", "fig", "banana", "kiwi"]
longs = [(w, L) for w in words if (L := len(w)) > 3]
print(longs)

a = {n for n in range(1, 30) if n % 3 == 0}
b = {n for n in range(1, 30) if n % 4 == 0}
print(sorted(a & b), sorted(a | b))
print(sorted(a ^ b), len(a - b))
frozen = frozenset({5, 1, 5, 3})
print(sorted(frozen), len(frozen))
print({1, 2}.issubset({1, 2, 3}), {9}.isdisjoint(a))

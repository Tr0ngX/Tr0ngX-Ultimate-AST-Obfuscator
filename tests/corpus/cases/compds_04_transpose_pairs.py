mat = [[1, 2, 3], [4, 5, 6]]
trans = [{mat[r][c] for r in range(len(mat))} for c in range(len(mat[0]))]
print([sorted(col) for col in trans])
pairs = {(x, y) for x in range(3) for y in range(3) if x < y}
print(sorted(pairs))
dedup = [frozenset(row) for row in mat]
print([sorted(fs) for fs in dedup])
lookup = {fs: len(fs) for fs in dedup}
print(sorted((tuple(sorted(k)), v) for k, v in lookup.items()))

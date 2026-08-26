port_map = {"http": 80, "https": 443, "ssh": 22, "dns": 53}
inverse = {v: k for k, v in port_map.items()}
print(dict(sorted(inverse.items())))
multi = {"a": [1, 2], "b": [3]}
flat = {item: key for key, vals in multi.items() for item in vals}
print(dict(sorted(flat.items())))
matrix = [[r * 3 + c for c in range(3)] for r in range(3)]
coords = {(r, c): matrix[r][c] for r in range(3) for c in range(3)}
print(coords[(2, 1)], sum(coords.values()))
filtered = {k: v for k, v in coords.items() if v % 2 == 0}
print(len(filtered), max(filtered.values()))
merged = {**inverse, 8080: "alt-http"}
print(len(merged))

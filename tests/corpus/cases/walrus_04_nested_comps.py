grid = [[1, 2], [3], [], [4, 5]]
flat_pairs = [
    (ri, ci, w)
    for ri, row in enumerate(grid)
    if (rl := len(row)) > 0
    for ci, v in enumerate(row)
    if (w := v * rl) % 2 == 0
]
print(flat_pairs)

data = ["aa", "bbb", "cccc"]
info = [
    (s, u, u * u)
    for s in data
    if (u := len(s)) >= 2
    if (u2 := u * u) > 4
]
print(info)

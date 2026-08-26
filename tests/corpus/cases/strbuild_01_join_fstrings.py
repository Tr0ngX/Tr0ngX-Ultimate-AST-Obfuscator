rows = [("amy", 91.5), ("bob", 78.25), ("cy", 84)]
lines = [f"{name:<6}|{score:07.2f}" for name, score in rows]
print("\n".join(lines))
print("-" * 13)
csv = ",".join(f"{n},{s:g}" for n, s in rows)
print(csv)
width = max(len(n) for n, _ in rows)
print(width)
print("|".join(n.center(width + 2) for n, _ in rows))

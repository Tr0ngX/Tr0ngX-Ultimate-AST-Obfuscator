rows = [
    ("id", "name", "score"),
    (1, "ada", 99.5),
    (22, "grace", 88.25),
    (333, "linus", 77.125),
]
widths = [max(len(str(r[i])) for r in rows) for i in range(3)]
fmt_rows = []
for r in rows:
    cells = []
    for i, cell in enumerate(r):
        if isinstance(cell, float):
            cells.append(f"{cell:>7.2f}")
        else:
            cells.append(str(cell).ljust(widths[i]))
    fmt_rows.append(" | ".join(cells))
print("\n".join(fmt_rows))
name = "Tr0ngX"
print(f"{name=:>10}", f"{name=!r:^12}", f"{name:*^16}")
pi = 3.14159265
print(f"{pi:.3f}|{pi:10.2f}|{pi:e}|{1000000:,}")
tmpl = "{who} did {what} in {when}".format(who="Ada", what="L", when="1843")
print(tmpl.title())

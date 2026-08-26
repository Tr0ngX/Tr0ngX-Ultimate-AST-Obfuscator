def describe(payload):
    match payload:
        case []:
            return "empty-list"
        case [x]:
            return f"single:{x}"
        case ["add", *rest]:
            return f"add:{len(rest)}"
        case [first, last]:
            return f"pair:{first}-{last}"
        case {"op": op, "args": [*args]} if op in ("mul", "div"):
            return f"{op}:{args}"
        case {"op": op}:
            return f"bare-op:{op}"
        case str() as s if s.startswith("!"):
            return f"bang:{s}"
        case _:
            return "?"


cases = [
    [],
    [7],
    ["add", 1, 2, 3],
    [1, 2],
    {"op": "mul", "args": [2, 5]},
    {"op": "mod"},
    "!alert",
    3.14,
]
for c in cases:
    print(describe(c))

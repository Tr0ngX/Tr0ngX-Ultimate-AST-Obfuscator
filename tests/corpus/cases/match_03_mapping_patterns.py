def route(cmd):
    match cmd:
        case {"op": "add", "a": a, "b": b}:
            return a + b
        case {"op": "mul", **rest} if "a" in rest and "b" in rest:
            return rest["a"] * rest["b"]
        case {"op": op, **rest}:
            return f"unknown:{op}:{sorted(rest)}"
        case _:
            return "malformed"


print(route({"op": "add", "a": 2, "b": 3}))
print(route({"op": "mul", "a": 4, "b": 5}))
print(route({"op": "pow", "a": 2}))
print(route([]))

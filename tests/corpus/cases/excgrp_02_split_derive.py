g = ExceptionGroup(
    "multi",
    [
        ValueError("v1"),
        TypeError("t1"),
        ValueError("v2"),
        KeyError("k"),
    ],
)

sub = g.subgroup(ValueError)
print(type(sub).__name__, sub.message, len(sub.exceptions))
print(sorted(type(e).__name__ for e in sub.exceptions))


def swap(exc):
    if isinstance(exc, ValueError):
        return RuntimeError(str(exc).upper())
    return exc


derived = g.derive(swap)
print(sorted(type(e).__name__ for e in derived.exceptions))

matched, rest = g.split(TypeError)
print(len(matched.exceptions), len(rest.exceptions))
print(matched.message, rest.message)

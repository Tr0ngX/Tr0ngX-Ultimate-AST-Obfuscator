class Point:
    __match_args__ = ("x", "y")

    def __init__(self, x, y):
        self.x, self.y = x, y


class Line:
    __match_args__ = ("a", "b")

    def __init__(self, a, b):
        self.a, self.b = a, b


def describe(obj):
    match obj:
        case Point(0, 0):
            return "origin"
        case Point(0, y):
            return f"y-axis:{y}"
        case Point(x, 0):
            return f"x-axis:{x}"
        case Point(x, y) if x == y:
            return "diagonal"
        case Line(Point() as p1, Point() as p2):
            return f"line:{p1.x}-{p2.x}"
        case Point() | Line():
            return "shape"
        case _:
            return "?"


probes = [
    Point(0, 0),
    Point(0, 5),
    Point(5, 0),
    Point(3, 3),
    Point(2, 9),
    Line(Point(1, 1), Point(2, 2)),
    "junk",
]
print([describe(p) for p in probes])

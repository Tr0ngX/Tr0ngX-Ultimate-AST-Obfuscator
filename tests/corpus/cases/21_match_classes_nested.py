class Point:
    __match_args__ = ("x", "y")

    def __init__(self, x, y):
        self.x, self.y = x, y


class Line:
    __match_args__ = ("start", "end")

    def __init__(self, start, end):
        self.start, self.end = start, end


def locate(obj):
    match obj:
        case Line(Point(0, 0) as origin, Point(x=x, y=y)):
            return f"origin-line:{x},{y}"
        case Line(Point(a, b), Point(a2, b2)) if a == a2:
            return f"vertical:{a}"
        case Point(x=0, y=y):
            return f"y-axis:{y}"
        case Point():
            return "point-elsewhere"
        case _:
            return "unknown"


items = [
    Line(Point(0, 0), Point(3, 4)),
    Line(Point(2, 1), Point(2, 9)),
    Point(0, -5),
    Point(6, 7),
    "junk",
]
for it in items:
    print(locate(it))

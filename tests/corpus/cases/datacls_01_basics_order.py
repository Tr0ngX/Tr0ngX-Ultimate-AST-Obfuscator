from dataclasses import dataclass, fields


@dataclass(order=True)
class Point:
    x: int
    y: int


pts = [Point(2, 3), Point(1, 1), Point(2, 2)]
print(pts)
print(sorted(pts))
print(Point(1, 2) == Point(1, 2))
print([f.name for f in fields(Point)])

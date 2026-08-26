from dataclasses import dataclass, field, replace, fields


@dataclass(frozen=True, order=True)
class Point:
    x: int = 0
    y: int = 0
    tags: tuple = field(default=(), compare=False)


pts = [Point(3, 4), Point(1, 9), Point(1, 2, tags=("a",))]
print(sorted(pts))
p2 = replace(pts[0], y=10)
print(p2, pts[0])
print(p2 == Point(3, 10))
print([f.name for f in fields(Point)])
try:
    pts[0].x = 99
except Exception as e:
    print(type(e).__name__)

from typing import TypedDict, NamedTuple, get_type_hints


class Movie(TypedDict):
    title: str
    year: int


class Point(NamedTuple):
    x: int
    y: int = 0


m: Movie = {"title": "Metropolis", "year": 1927}
print(m["title"], Movie.__annotations__["year"].__name__)
hints = get_type_hints(Movie)
print(sorted(hints), hints["title"].__name__)
p = Point(3)
print(p, p._fields, p._asdict()["x"])
print(isinstance(p, tuple), Point(1, 2)._replace(y=9).y)
print(Point.__annotations__["x"].__name__)

import typing


class Movie(typing.TypedDict):
    title: str
    year: int


print(sorted(Movie.__annotations__))
print(Movie.__required_keys__ == frozenset({"title", "year"}))
mv: Movie = {"title": "Metropolis", "year": 1927}
print(mv["title"], mv["year"])
print(typing.get_type_hints(Movie)["year"].__name__)

Point = typing.NamedTuple("Point", [("x", int), ("y", int)])
p = Point(3, 4)
print(p, p.x + p.y, Point.__annotations__["x"].__name__)
print(isinstance(p, tuple))

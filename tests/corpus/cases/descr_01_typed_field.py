class Typed:
    def __init__(self, typ):
        self.typ = typ

    def __set_name__(self, owner, name):
        self.name = "_" + name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.name, None)

    def __set__(self, obj, value):
        if not isinstance(value, self.typ):
            raise TypeError(f"{self.name} expects {self.typ.__name__}")
        setattr(obj, self.name, value)


class Point:
    x = Typed(int)
    y = Typed(int)


p = Point()
p.x, p.y = 3, 4
print(p.x * p.y)
try:
    p.x = "bad"
except TypeError as e:
    print("TypeError:", e)
print(Point.y is not None)

class Vec:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x, self.y = x, y

    def dot(self, other):
        return self.x * other.x + self.y * other.y

    def __repr__(self):
        return f"Vec({self.x},{self.y})"


a, b = Vec(2, 3), Vec(4, 5)
print(a.dot(b), Vec.__slots__)
print(repr(a))
try:
    a.z = 9
except AttributeError:
    print("AttributeError")
print(getattr(Vec, "__dict__").get("__slots__") is not None)

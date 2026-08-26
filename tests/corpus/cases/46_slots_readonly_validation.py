class Vec3:
    __slots__ = ("x", "y", "z")

    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __repr__(self):
        return f"Vec3({self.x:g}, {self.y:g}, {self.z:g})"

    def dot(self, o):
        return self.x * o.x + self.y * o.y + self.z * o.z

    def norm(self):
        m = (self.dot(self)) ** 0.5
        return Vec3(self.x / m, self.y / m, self.z / m)


a = Vec3(1, 2, 2)
print(a, a.dot(Vec3(2, 0, 0)), round(a.norm().z, 4))
try:
    a.w = 5
except AttributeError:
    print("no-new-attrs")
b = Vec3(3, 4, 0)
print(round(b.norm().x, 3), round(b.norm().y, 3))
print(Vec3.__slots__ is Vec3.__slots__, a.__slots__ is Vec3.__slots__)

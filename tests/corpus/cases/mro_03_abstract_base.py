from abc import ABC, abstractmethod


class Shape(ABC):
    @abstractmethod
    def area(self): ...

    def describe(self):
        return f"{type(self).__name__}:{self.area():.1f}"


class Sq(Shape):
    def __init__(self, s):
        self.s = s

    def area(self):
        return float(self.s ** 2)


class Ci(Shape):
    def __init__(self, r):
        self.r = r

    def area(self):
        return 3.14159 * self.r ** 2


shapes = [Sq(3), Ci(1)]
print([s.describe() for s in shapes])
try:
    Shape()
except TypeError as e:
    print("TypeError:", str(e)[:40])
print(issubclass(Sq, Shape), isinstance(Ci(1), Shape))

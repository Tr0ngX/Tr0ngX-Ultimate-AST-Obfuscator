import functools


class ValidatedMethod:
    def __init__(self, func):
        functools.update_wrapper(self, func)
        self.func = func
        self.calls = 0

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        self.calls += 1
        return self.func(obj)


class Circle:
    def __init__(self, r):
        self.r = r

    @ValidatedMethod
    def area(self):
        return 3 * self.r * self.r


c = Circle(2)
print(c.area(), c.area(), c.area())
print(Circle.area.func.__name__)
print(Circle.area.calls)
print(c.area.calls)

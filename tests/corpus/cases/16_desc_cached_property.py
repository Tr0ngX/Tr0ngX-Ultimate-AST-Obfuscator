class CachedProperty:
    def __init__(self, func):
        self.func = func
        self.attr = func.__name__
        self.__doc__ = func.__doc__

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        val = self.func(obj)
        obj.__dict__[self.attr] = val
        return val


class Circle:
    def __init__(self, r):
        self.r = r

    @CachedProperty
    def area(self):
        print("computing area")
        return 3 * self.r ** 2


c = Circle(4)
print(c.area)
print(c.area)
d = Circle(2)
print(d.area)
print(type(Circle.area).__name__)
print("area" in c.__dict__, "area" in d.__dict__)

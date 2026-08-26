import functools


class CountCalls:
    instances = []

    def __init__(self, func):
        functools.update_wrapper(self, func)
        self.func = func
        self.count = 0
        CountCalls.instances.append(self)

    def __get__(self, obj, objtype=None):
        return functools.partial(self.__call__, obj)

    def __call__(self, *a, **k):
        self.count += 1
        return self.func(*a, **k)


class Registry:
    @CountCalls
    def lookup(self, key):
        return f"<{key}>"


r1 = Registry()
r2 = Registry()
print(r1.lookup("a"), r2.lookup("b"), r1.lookup("c"))
inst = CountCalls.instances[-1]
print(inst.count)
print(inst.__name__)

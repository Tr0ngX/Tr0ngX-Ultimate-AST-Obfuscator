class OrderedNS(dict):
    pass


class Meta(type):
    @classmethod
    def __prepare__(mcs, name, bases, **kw):
        ns = OrderedNS()
        ns["_marker"] = "prepared:" + name
        return ns

    def __new__(mcs, name, bases, ns, **kw):
        cls = super().__new__(mcs, name, bases, dict(ns))
        cls._order = [k for k in ns if not k.startswith("__")]
        return cls


class Widget(metaclass=Meta):
    alpha = 1
    beta = 2
    gamma = 3


print(type(Widget).__name__)
print(Widget._order)
print(Widget._marker)

class Registered(type):
    @staticmethod
    def __prepare__(name, bases, **kwds):
        ns = {"kind": name.lower(), "registry": []}
        ns["prepared_by"] = "Registered"
        return ns

    def __new__(mcls, name, bases, ns, **kwds):
        cls = super().__new__(mcls, name, bases, ns)
        cls.registry.append(cls)
        return cls


class Service(metaclass=Registered):
    tag = "svc"

    def ping(self):
        return f"{self.kind}:{self.tag}"


class Cache(Service):
    tag = "cache"


print(Service.kind, Cache.prepared_by)
print(Service().ping(), Cache().ping())
print([c.__name__ for c in Service.registry])
print(Cache.registry is Service.registry)

class Mixin:
    def setup(self, parts=None):
        parts = [] if parts is None else parts
        parts.append("base")
        return parts


class Logging(Mixin):
    def setup(self, parts=None):
        parts = super().setup(parts)
        parts.insert(0, "log")
        return parts


class Metrics(Mixin):
    def setup(self, parts=None):
        parts = super().setup(parts)
        parts.append("metrics")
        return parts


class Service(Logging, Metrics):
    pass


print(Service().setup())
print([c.__name__ for c in Service.__mro__[:4]])

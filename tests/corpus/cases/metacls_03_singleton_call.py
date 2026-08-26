class Singleton(type):
    _instances = {}
    _count = {}

    def __call__(cls, *args, **kw):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kw)
            cls._count[cls] = 0
        cls._count[cls] += 1
        return cls._instances[cls]


class Config(metaclass=Singleton):
    def __init__(self):
        self.data = [1]


a = Config()
b = Config()
print(a is b)
print(Singleton._count[Config])
a.data.append(2)
print(Config().data)

events = []


class Track(type):
    def __prepare__(name, bases):
        events.append(f"prepare:{name}")
        return {}

    def __new__(mcls, name, bases, ns):
        events.append(f"new:{name}")
        return super().__new__(mcls, name, bases, ns)

    def __init__(cls, name, bases, ns):
        events.append(f"init:{name}")
        super().__init__(name, bases, ns)


class Field(metaclass=Track):
    def __set_name__(self, owner, name):
        events.append(f"desc-setname:{owner.__name__}.{name}")


class Model(metaclass=Track):
    alpha = Field()
    beta = Field()


print(events)
print(type(Model.alpha).__name__, Model.alpha is Model.beta)

class RegistryMeta(type):
    registry = {}

    def __new__(mcs, name, bases, ns):
        cls = super().__new__(mcs, name, bases, ns)
        if bases:
            mcs.registry[name.lower()] = cls
        return cls


class Animal(metaclass=RegistryMeta):
    pass


class Dog(Animal):
    sound = "woof"


class Cat(Animal):
    sound = "meow"


keys = sorted(RegistryMeta.registry)
print(keys)
print([RegistryMeta.registry[k]().sound for k in keys])

class Guarded:
    def __init__(self, initial=None):
        self.value = initial

    def __get__(self, obj, objtype=None):
        if obj is None:
            return "<descriptor>"
        return self.value

    def __set__(self, obj, value):
        if self.value is None:
            self.value = value
        else:
            raise AttributeError("already set")

    def __delete__(self, obj):
        self.value = None


class Slot:
    token = Guarded()


s = Slot()
s.token = "abc"
print(s.token)
try:
    s.token = "xyz"
except AttributeError as e:
    print(e)
del s.token
print(s.token)
Slot.token = "class-level"
print(Slot.token)

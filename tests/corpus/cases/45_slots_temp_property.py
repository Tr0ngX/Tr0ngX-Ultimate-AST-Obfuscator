class Celsius:
    __slots__ = ("_c",)

    def __init__(self, c):
        self.c = c

    @property
    def c(self):
        return self._c

    @c.setter
    def c(self, value):
        if value < -273.15:
            raise ValueError("below absolute zero")
        self._c = value

    @property
    def f(self):
        return self._c * 9 / 5 + 32


t = Celsius(25)
print(round(t.f, 2))
t.c = -40
print(t.c, t.f)
print(Celsius.__slots__, hasattr(t, "__dict__"))
try:
    t.kelvin = 300
except AttributeError as e:
    print("slots-block:", "kelvin" in str(e))
try:
    t.c = -300
except ValueError as e:
    print("range-guard:", e)

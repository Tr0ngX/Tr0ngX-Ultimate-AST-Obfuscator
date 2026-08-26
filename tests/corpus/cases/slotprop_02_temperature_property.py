class Temp:
    def __init__(self, c):
        self.celsius = c

    @property
    def celsius(self):
        return self._c

    @celsius.setter
    def celsius(self, v):
        if v < -273.15:
            raise ValueError("below absolute zero")
        self._c = float(v)

    @property
    def fahrenheit(self):
        return self._c * 9 / 5 + 32


t = Temp(100)
print(round(t.fahrenheit, 1))
t.celsius = -40
print(t.celsius, round(t.fahrenheit, 1))
try:
    t.celsius = -300
except ValueError as e:
    print("ValueError:", e)
print(type(Temp.fahrenheit).__name__)

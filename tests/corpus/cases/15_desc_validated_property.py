class Bounded:
    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__[f"_{self.name}"]

    def __set__(self, obj, value):
        if not (self.lo <= value <= self.hi):
            raise ValueError(f"{self.name}={value} outside [{self.lo},{self.hi}]")
        obj.__dict__[f"_{self.name}"] = value


class Recipe:
    temp = Bounded(0, 300)
    minutes = Bounded(0, 120)

    def __init__(self, temp, minutes):
        self.temp = temp
        self.minutes = minutes


r = Recipe(180, 45)
print(r.temp, r.minutes)
r.minutes += 15
print(r.temp, r.minutes)
print(Recipe.temp.name, Recipe.minutes.lo)
try:
    r.temp = 999
except ValueError as e:
    print("rejected:", e)
print(r.__dict__)

import pickle
import copy


class Chip:
    __slots__ = ("cores", "clock")

    def __init__(self, cores, clock):
        self.cores, self.clock = cores, clock

    def __eq__(self, o):
        return (self.cores, self.clock) == (o.cores, o.clock)


c1 = Chip(8, 3.4)
blob = pickle.dumps(c1)
c2 = pickle.loads(blob)
c3 = copy.copy(c1)
c4 = copy.deepcopy(c1)
print(c1 == c2, c1 == c3, c1 == c4)
c2.cores = 16
print(c1 == c2, c2.cores, c2.clock)
try:
    c2.gpu = True
except AttributeError:
    print("pickle-keeps-slots")
print(len(pickle.dumps(c1)) > 0, Chip.__slots__)

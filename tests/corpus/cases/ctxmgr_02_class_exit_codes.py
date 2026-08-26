class Resource:
    opened = 0
    closed = 0

    def __init__(self, name, suppress=False):
        self.name = name
        self.suppress = suppress

    def __enter__(self):
        Resource.opened += 1
        return self

    def __exit__(self, et, ev, tb):
        Resource.closed += 1
        label = et.__name__ if et else "clean"
        print(f"exit:{self.name}:{label}")
        return bool(et) and self.suppress


with Resource("a"):
    pass

with Resource("b", suppress=True):
    raise ValueError("swallowed")

try:
    with Resource("c"):
        raise KeyError("leaks")
except KeyError as e:
    print("caught:", str(e))

print(Resource.opened, Resource.closed)

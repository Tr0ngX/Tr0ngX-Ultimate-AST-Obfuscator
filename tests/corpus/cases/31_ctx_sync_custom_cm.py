class Resource:
    def __init__(self, name, log):
        self.name = name
        self.log = log

    def __enter__(self):
        self.log.append(f"+{self.name}")
        return self

    def __exit__(self, et, ev, tb):
        self.log.append(f"-{self.name}({'exc' if et else 'ok'})")
        return False


log = []
with Resource("A", log) as a, Resource("B", log) as b:
    log.append(f"use {a.name}{b.name}")
try:
    with Resource("C", log), Resource("D", log):
        raise RuntimeError("mid")
except RuntimeError as e:
    log.append(f"caught:{e}")
print(log)

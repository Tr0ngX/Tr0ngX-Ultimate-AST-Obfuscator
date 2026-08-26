from contextlib import contextmanager, suppress

log = []


@contextmanager
def stage(label):
    log.append(f"enter:{label}")
    try:
        yield label.upper()
    except ValueError as e:
        log.append(f"swallowed:{label}:{e}")
    finally:
        log.append(f"exit:{label}")


with stage("one") as s:
    log.append(s)
with stage("two"):
    raise ValueError("oops")
with suppress(KeyError):
    raise KeyError("ignored")
log.append("after-suppress")
try:
    with stage("three"):
        raise TypeError("not swallowed")
except TypeError as e:
    log.append(f"propagated:{e}")
print(log)

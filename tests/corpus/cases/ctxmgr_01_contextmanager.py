from contextlib import contextmanager

log = []


@contextmanager
def stage(name):
    log.append("enter:" + name)
    try:
        yield name.upper()
    except RuntimeError:
        log.append("handled:" + name)
        raise
    finally:
        log.append("exit:" + name)


with stage("boot") as s:
    log.append("body:" + s)

try:
    with stage("risk"):
        raise RuntimeError("boom")
except RuntimeError:
    pass

print(log)

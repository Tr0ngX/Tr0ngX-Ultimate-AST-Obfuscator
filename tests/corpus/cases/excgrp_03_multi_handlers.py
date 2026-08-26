def batch():
    raise ExceptionGroup(
        "batch",
        [
            ValueError("bad-input"),
            OSError("disk-full"),
            ValueError("worse-input"),
        ],
    )


try:
    batch()
except* OSError as og:
    print("os:", [str(e) for e in og.exceptions])
except* ValueError as vg:
    print("val:", [str(e) for e in vg.exceptions])
except* KeyError:
    print("unreachable")

try:
    batch()
except* (OSError, ValueError) as combined:
    print("combined:", len(combined.exceptions))

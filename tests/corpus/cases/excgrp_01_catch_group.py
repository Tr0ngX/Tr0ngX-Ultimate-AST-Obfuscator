def parse(raw):
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise ExceptionGroup("conversion failed", [exc]) from None


for raw in ["42", "nope", "  7  ", ""]:
    try:
        print(parse(raw))
    except* ValueError as eg:
        print("group:", eg.message, len(eg.exceptions))

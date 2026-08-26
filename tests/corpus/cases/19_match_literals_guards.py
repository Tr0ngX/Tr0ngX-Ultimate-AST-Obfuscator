def classify(code):
    match code:
        case 0:
            return "zero"
        case 200 | 201 | 204:
            return "success"
        case 404:
            return "missing"
        case n if n >= 500:
            return f"server-error-{n}"
        case n if 400 <= n < 500:
            return "client-error"
        case _:
            return "other"


for c in (0, 204, 404, 503, 418, 302):
    print(c, classify(c))

def classify(x):
    match x:
        case 0:
            return "zero"
        case n if n < 0:
            return "negative"
        case n if n % 2 == 0:
            return "even"
        case _:
            return "odd"


print([classify(i) for i in (-3, 0, 4, 7)])

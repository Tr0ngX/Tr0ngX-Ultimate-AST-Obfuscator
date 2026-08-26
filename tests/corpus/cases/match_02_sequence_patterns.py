def head_rest(seq):
    match seq:
        case []:
            return "empty"
        case [only]:
            return f"one:{only}"
        case [first, second]:
            return f"two:{first},{second}"
        case [first, *rest]:
            return f"many:{first},rest={rest}"
        case _:
            return "not-seq"


for probe in ([], [9], [1, 2], [1, 2, 3, 4]):
    print(head_rest(probe))

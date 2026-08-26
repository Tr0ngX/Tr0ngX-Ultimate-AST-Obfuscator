class NetErr(Exception):
    pass


class DbErr(Exception):
    pass


class AuthErr(Exception):
    pass


def load(i):
    errs = {0: NetErr("net-down"), 1: DbErr("db-lock"), 2: AuthErr("bad-token")}
    if i in errs:
        raise errs[i]
    return f"data-{i}"


results = []
for i in range(5):
    try:
        results.append(load(i))
    except* NetErr as eg:
        results.append("NET:" + str(eg.exceptions[0]))
    except* DbErr as eg:
        results.append("DB:" + str(eg.exceptions[0]))
    except* AuthErr:
        results.append("AUTH")
print(results)

try:
    try:
        raise ExceptionGroup("batch", [NetErr("a"), DbErr("b"), NetErr("c")])
    except* NetErr as eg:
        print("net handled:", len(eg.exceptions))
except* DbErr as eg:
    print("db escaped:", len(eg.exceptions))
finally:
    print("finally ran")

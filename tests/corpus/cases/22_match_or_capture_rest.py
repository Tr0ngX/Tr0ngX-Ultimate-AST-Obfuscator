def route(cmd):
    match cmd.split():
        case ["help" | "h"]:
            return "show help"
        case ["go", ("north" | "up")]:
            return "going north"
        case ["go", direction]:
            return f"go:{direction}"
        case ["drop", *objects, "here"]:
            return f"drop {len(objects)} here"
        case ["take", obj, "times", n] if n.isdigit():
            return f"take {obj} x{int(n)}"
        case []:
            return "noop"
        case words:
            return f"unparsed:{'-'.join(words)}"


cmds = [
    "h",
    "go up",
    "go sideways",
    "drop sword shield here",
    "take apple times 3",
    "",
    "dance now",
]
for c in cmds:
    print(route(c))

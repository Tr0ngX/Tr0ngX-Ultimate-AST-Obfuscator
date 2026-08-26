py_devs = {"ann", "bob", "cy", "dee", "eli"}
rust_devs = {"bob", "dee", "fin", "gia"}
both = py_devs & rust_devs
only_py = py_devs - rust_devs
either = py_devs ^ rust_devs
print(sorted(both), sorted(only_py), sorted(either))
print(py_devs >= both, rust_devs.isdisjoint({"zzz"}))
lengths = {len(w) for w in py_devs}
print(sorted(lengths))
fro = frozenset(["x", "y"])
print(sorted(py_devs | fro), fro <= py_devs | fro)
print(sorted(py_devs.symmetric_difference(rust_devs)) == sorted(either))

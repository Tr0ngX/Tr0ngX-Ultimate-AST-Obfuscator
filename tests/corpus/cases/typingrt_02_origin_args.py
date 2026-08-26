import typing

T = typing.List[typing.Optional[int]]
print(typing.get_origin(T).__name__)
inner = typing.get_args(T)[0]
print(typing.get_origin(inner).__name__, typing.get_args(inner))

M = typing.Dict[str, typing.Tuple[int, ...]]
ma = typing.get_args(M)
print(ma[0].__name__, typing.get_args(ma[1]))

U = typing.Union[int, str, None]
print(typing.get_origin(U) is typing.Union, len(typing.get_args(U)))

V = typing.Callable[[int, str], bool]
print(typing.get_origin(V).__name__, typing.get_args(V)[-1].__name__)

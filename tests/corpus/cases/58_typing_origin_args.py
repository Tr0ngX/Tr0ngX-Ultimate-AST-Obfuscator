import typing
from typing import Union, Optional, List, Tuple, Callable, Dict, get_origin, get_args

sig = List[Dict[str, int]]
args = get_args(sig)
print(get_origin(sig).__name__, [type(a).__name__ for a in args])
opt = Optional[int]
print(opt == Union[int, None], get_args(opt))
tup = Tuple[int, ...]
print(get_origin(tup).__name__, get_args(tup))
cb = Callable[[str, int], bool]
print(get_origin(cb).__name__, len(get_args(cb)))
raw_union = Union[int, str, bytes]
print(raw_union == Union[str, bytes, int])
print(isinstance([], list), isinstance(typing.List, type))
print(get_origin(typing.Dict[str, int]).__name__)
print(get_args(Union[int, str]) == get_args(Union[str, int]))

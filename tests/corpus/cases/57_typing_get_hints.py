from typing import get_type_hints, List, Dict, Optional


class Config:
    name: str
    retries: int = 3
    tags: List[str] = None


def handler(user_id: int, payload: Dict[str, Optional[int]]) -> bool:
    return True


hints = get_type_hints(handler)
print(hints["user_id"].__name__, hints["return"].__name__)
module_hints = get_type_hints(Config)
print(sorted(module_hints))
print(module_hints["tags"].__origin__.__name__)
print(Config.__annotations__["retries"].__name__, Config.retries)
print(get_type_hints(handler, include_extras=False)["payload"].__origin__.__name__)

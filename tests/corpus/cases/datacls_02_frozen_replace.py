from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Version:
    major: int = 0
    minor: int = 1
    patch: int = 0

    @property
    def label(self):
        return f"v{self.major}.{self.minor}.{self.patch}"


v = Version(1, 4, 2)
print(v.label)
v2 = replace(v, patch=9)
print(v2.label)
print(hash(v) == hash(Version(1, 4, 2)))
try:
    v.patch = 5
except Exception as e:
    print(type(e).__name__)

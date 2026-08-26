class Field:
    def __set_name__(self, owner, name):
        self.attr = "_" + name
        owner._fields = [*getattr(owner, "_fields", []), name]

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.attr, None)

    def __set__(self, obj, value):
        setattr(obj, self.attr, value)


class Row:
    x = Field()
    y = Field()


r = Row()
r.x = 10
r.y = 20
print(Row._fields)
print(r.x + r.y)
print(Field.__get__(Row.x, None) is Row.x)

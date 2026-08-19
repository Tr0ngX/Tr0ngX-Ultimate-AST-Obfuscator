test_code = 'print(sum(range(1000)))'
key = 12345
alpha = 'abcdefghijklmnopqrstuvwxyz0123456789'
_2_stmt = f'''lambda _n1_:__import__('builtins').exec(_n1_)'''

# Let's test the entire Kramer class execution
_vars_ = f'''_n4_ = eval
_n7_ = '{alpha}'
_n5_ = lambda _n9_:__import__(_n7_[1]+_n7_[8]+_n7_[13]+_n7_[0]+_n7_[18]+_n7_[2]+_n7_[8]+_n7_[8]).unhexlify(str(_n9_)).decode()
_n6_ = lambda _n1_:_n4_(f"exec(_n1_)")
_n1_ = lambda _n1_:"".join(chr(ord(t)-{key})if t!="ζ"else"\\n"for t in _n5_(_n1_)).translate(str.maketrans(dict(zip(_n7_,_n7_[1:]+_n7_[:1]))))
_n8_ = lambda _n12_:_n6_(_n1_(_n12_))'''

print('Vars definition is clean and compact!')

_n7_ = 'abcdefghijklmnopqrstuvwxyz0123456789'
s_exec = _n7_[4]+_n7_[-13]+_n7_[4]+_n7_[2]
s_glob = _n7_[6]+_n7_[11]+_n7_[14]+_n7_[1]+_n7_[0]+_n7_[11]+_n7_[18]
print('s_exec:', s_exec, 's_glob:', s_glob)
# Test eval(f'exec(_n1_,globals())')
_n1_ = 'print(12345)'
_n4_ = [0, 0, eval]
_n2_ = 2
res = _n4_[_n2_](f\"{s_exec}(_n1_,{s_glob}())\")
print('Result of eval:', res)

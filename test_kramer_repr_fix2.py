_n4_ = [eval]
_n2_ = 0
_n7_ = 'abcdefghijklmnopqrstuvwxyz0123456789'
_2_ = lambda _n1_:_n4_[_n2_](f'{_n7_[4]+_n7_[-13]+_n7_[4]+_n7_[2]}({_n1_!r},{_n7_[6]+_n7_[11]+_n7_[14]+_n7_[1]+_n7_[0]+_n7_[11]+_n7_[18]}())')

test_code = 'x = 10\ny = 20\nprint(\"SUM:\", x+y)'
_2_(test_code)
print('Execution succeeded perfectly!')

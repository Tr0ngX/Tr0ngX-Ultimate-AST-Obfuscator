import os, sys

def fix_matrix_and_velimatix(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Fix _0x4 = {{}} in _velimatix_compile
    content = content.replace("_0x4 = {{}}", "_0x4 = dict()")

    # 2. Fix variable replacement collision in _fused_matrix_wrap
    old_fused_return = """    loader = fr\"\"\"class {c_name}():
 def {m_dec}(self:object,*_n2_:{random.choice(_types_)},**_n4_:{random.choice(_types_)})->exec:
  {_vars_}
  return _n8_({k_sparkle}, {k_emoji}, {k_ws})
 def {m_init}(self:object,_n1_:{random.choice(_types_)}=False,_n2_:{random.choice(_types_)}=0,*_n3_:{random.choice(_types_)},**_n4_:{random.choice(_types_)})->exec:
  self.{m_dec}(**_n4_)
{c_name}(_n1_=False,_n2_=0,_sparkle={sk!r},_emoji={se!r},_whitespace={sw!r})\"\"\".strip().replace('_n1_',glob['n_1'].removeprefix('self.')).replace('_n2_',glob['n_2'].removeprefix('self.')).replace('_n3_',glob['n_3'].removeprefix('self.')).replace('_n4_',glob['n_4'].removeprefix('self.')).replace('_n5_',glob['n_5']).replace('_n6_',glob['n_6']).replace('_n7_',glob['n_7']).replace('_n8_',glob['n_8'])"""

    new_fused_return = """    tmpl = fr\"\"\"class {c_name}():
 def {m_dec}(self:object,*_n2_:{random.choice(_types_)},**_n4_:{random.choice(_types_)})->exec:
  {_vars_}
  return _n8_({k_sparkle}, {k_emoji}, {k_ws})
 def {m_init}(self:object,_n1_:{random.choice(_types_)}=False,_n2_:{random.choice(_types_)}=0,*_n3_:{random.choice(_types_)},**_n4_:{random.choice(_types_)})->exec:
  self.{m_dec}(**_n4_)
{c_name}(_n1_=False,_n2_=0,_sparkle=__SPK_DATA__,_emoji=__EMJ_DATA__,_whitespace=__WSP_DATA__)\"\"\".strip()
    tmpl = tmpl.replace('_n1_', glob['n_1'].removeprefix('self.'))
    tmpl = tmpl.replace('_n2_', glob['n_2'].removeprefix('self.'))
    tmpl = tmpl.replace('_n3_', glob['n_3'].removeprefix('self.'))
    tmpl = tmpl.replace('_n4_', glob['n_4'].removeprefix('self.'))
    tmpl = tmpl.replace('_n5_', glob['n_5'])
    tmpl = tmpl.replace('_n6_', glob['n_6'])
    tmpl = tmpl.replace('_n7_', glob['n_7'])
    tmpl = tmpl.replace('_n8_', glob['n_8'])
    loader = tmpl.replace('__SPK_DATA__', repr(sk)).replace('__EMJ_DATA__', repr(se)).replace('__WSP_DATA__', repr(sw))"""

    content = content.replace(old_fused_return, new_fused_return)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

fix_matrix_and_velimatix(r"C:\Users\trong\Downloads\Kramer-main\Kramer-main\tr0ngx_obfuscator.py")
fix_matrix_and_velimatix(r"C:\Users\trong\Downloads\procheck.py")
print("Fixed _0x4 dict and ciphertext token replacement safety!")

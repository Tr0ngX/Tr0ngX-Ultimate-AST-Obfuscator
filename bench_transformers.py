import sys
sys.path.insert(0, r'C:\Users\trong\Downloads')
import procheck
import time
import ast

with open('complex_benchmark.py', 'r', encoding='utf-8-sig') as f:
    orig = f.read().lstrip('\ufeff')

c = procheck._syntax(orig)
c = procheck.__moreobf(c)
c = procheck.anti + c
c = procheck.velimatix_anti_hook + c
c = procheck._generate_self_modify_wrapper() + c

alphabet = 'Ox123456'
length = 17

tree = ast.parse(c)
tree = procheck.OBF_Formatter().visit(tree)
print('OBF_Formatter done')

t0 = time.time()
trans = procheck.BiOpaqueTransformer(alphabet, length, safe_mode=True)
tree = trans.proceed(tree)
print(f'BiOpaque: {time.time()-t0:.2f}s')

t0 = time.time()
trans = procheck.CallTransformer()
tree = trans.proceed(tree)
print(f'CallTrans: {time.time()-t0:.2f}s')

t0 = time.time()
trans = procheck.DeadCodeInjector(alphabet, length, density=3)
tree = trans.proceed(tree)
print(f'DeadCode: {time.time()-t0:.2f}s')

t0 = time.time()
trans = procheck.ExceptionJumpTransformer(alphabet, length)
tree = trans.proceed(tree)
print(f'ExceptionJump: {time.time()-t0:.2f}s')

t0 = time.time()
trans = procheck.BuiltinRenamerTransformer(alphabet, length)
tree = trans.proceed(tree)
print(f'BuiltinRenamer: {time.time()-t0:.2f}s')

t0 = time.time()
trans = procheck.ControlFlowTransformer(alphabet, length)
tree = trans.proceed(tree)
print(f'ControlFlow: {time.time()-t0:.2f}s')

t0 = time.time()
trans = procheck.MutatorTransformer(alphabet, length, ladder=2)
tree = trans.proceed(tree)
print(f'Mutator: {time.time()-t0:.2f}s')

t0 = time.time()
trans = procheck.MethodClonerTransformer(alphabet, length, count=4)
tree = trans.proceed(tree)
print(f'MethodCloner: {time.time()-t0:.2f}s')

t0 = time.time()
trans = procheck.StringEncoderTransformer()
tree = trans.proceed(tree)
print(f'StringEncoder: {time.time()-t0:.2f}s')

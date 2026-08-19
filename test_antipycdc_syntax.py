s = '''def 你器(你):
    return 你
try:pass
except:pass
finally:pass
try:trongdepzai=[你器(''),]
except:pass
finally:int(2008-2006)
'''
try:
    compile(s, '<test>', 'exec')
    print('Valid Python!')
except Exception as e:
    print('SyntaxError:', e)

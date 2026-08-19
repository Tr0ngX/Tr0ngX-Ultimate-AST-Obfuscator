with open('obf_final.py', 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

print('File length:', len(text))
t0 = time.time()
p_count = text.count('print')
i_count = text.count('input')
print(f'Done reading in {time.time()-t0:.2f}s! print count = {p_count}, input count = {i_count}')

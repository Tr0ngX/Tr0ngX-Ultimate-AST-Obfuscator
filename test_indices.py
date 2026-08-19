alpha = 'abcdefghijklmnopqrstuvwxyz0123456789'
print('Indices for _2_:')
print('func:', alpha[4] + alpha[-13] + alpha[4] + alpha[2]) # exec
print('globals:', alpha[6] + alpha[11] + alpha[14] + alpha[1] + alpha[0] + alpha[11] + alpha[18]) # globals
print('encoding:', alpha[20] + alpha[19] + alpha[5] + alpha[34]) # utf8

print('\nIndices for _4_ anti-tamper:')
print('word 1:', alpha[15] + alpha[17] + alpha[8] + alpha[13] + alpha[19]) # print
print('word 2:', alpha[8] + alpha[13] + alpha[15] + alpha[20] + alpha[19]) # input
print('errors:', alpha[8] + alpha[6] + alpha[13] + alpha[14] + alpha[17] + alpha[4]) # ignore

print('\nIndices for _final_content_:')
print('kwarg:', (alpha[-1]+'_')[-1] + alpha[18] + alpha[15] + alpha[0] + alpha[17] + alpha[10] + alpha[11] + alpha[4])

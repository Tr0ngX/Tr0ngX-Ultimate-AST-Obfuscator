# Let's test the original try/catch structure:
# try:
#     match var1 == var2:
#         case True: raise MemoryError(True)
#         case False: pass
# except MemoryError as err:
#     STATEMENT
#     raise MemoryError(True)
# If var1 != var2 (which is 98% probability), it goes to case False -> does NOT raise MemoryError!
# Then the try block finishes without error, skipping the except block (which contains STATEMENT)!
# And then the unhandled MemoryError(True) gets raised after the try block, crashing the script!
print('Discovered logic flaw in original trycatch structure!')

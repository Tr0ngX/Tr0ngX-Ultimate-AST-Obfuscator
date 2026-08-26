from string import Template

t = Template("$who owes $$${amount}")
print(t.substitute(who="lee", amount=42))
safe = Template("${name}'s score: $score")
print(safe.safe_substitute(name="kim", score=99, extra="ignored"))

print("{:>8}{:^8}{:<8}".format("left", "mid", "right"))
print("{0:b} {0:o} {0:x}".format(255))
print("{:.2e}".format(12345.678))
print("{:*^12}".format("cut"))

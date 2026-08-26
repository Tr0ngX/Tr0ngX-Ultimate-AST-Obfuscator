import textwrap

sample = (
    "The quick brown fox jumps over the lazy dog "
    "while measuring string building pipelines."
)
print(textwrap.wrap(sample, width=24))
print(textwrap.fill(sample, width=30))
print(textwrap.shorten(sample, width=40, placeholder=" [...]"))
block = """
    line one
      line two indented
"""
print(textwrap.dedent(block).strip().replace("\n", "|"))

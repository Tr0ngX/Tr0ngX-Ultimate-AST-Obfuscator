docs = {
    "d1": "apple banana apple",
    "d2": "banana cherry",
    "d3": "apple dog",
}
index = {}
for doc, body in docs.items():
    for term in body.split():
        index.setdefault(term, set()).add(doc)
print({t: sorted(ds) for t, ds in sorted(index.items())})
both = sorted(t for t, ds in index.items() if len(ds) >= 2)
print(both)
sizes = {doc: len(body.split()) for doc, body in docs.items()}
print(sizes)

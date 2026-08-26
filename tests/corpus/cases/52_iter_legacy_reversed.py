class Deck:
    def __init__(self):
        self.cards = list(range(1, 6))

    def __len__(self):
        return len(self.cards)

    def __getitem__(self, i):
        return self.cards[i]


deck = Deck()
print(list(deck))
print(list(reversed(deck)))
print(deck[1], deck[-1], len(deck))
print(max(deck), sum(deck))


class Squares:
    def __getitem__(self, i):
        if i >= 5:
            raise IndexError
        return i * i


print(list(Squares()), list(iter(Squares()))[:3])

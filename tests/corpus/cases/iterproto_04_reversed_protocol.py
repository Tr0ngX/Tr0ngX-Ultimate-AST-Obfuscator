class Playlist:
    def __init__(self, songs):
        self._songs = list(songs)

    def __iter__(self):
        return iter(self._songs)

    def __len__(self):
        return len(self._songs)

    def __getitem__(self, i):
        return self._songs[i]

    def __reversed__(self):
        return iter(list(reversed(self._songs)))


pl = Playlist(["a", "b", "c", "d"])
print(list(pl))
print(list(reversed(pl)))
pl2 = Playlist(range(4))
print([x for x in pl2][::-1])
print(len(pl2))

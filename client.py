import torrent

t = torrent.Torrent('oz.torrent')
print(t.info_hash)
print(t.length)
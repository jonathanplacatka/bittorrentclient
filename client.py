import torrent
import random

t = torrent.Torrent('oz.torrent')
print(t.info_hash)
print(t.length)

#20 bytes: 2 for client id, 4 for version number, remaining are random integers
def generate_peer_id():
    id = 'SY1000' 
    for k in range(0, 14):
        id += str(random.randint(0,9))
    return id

def get_peer_list():
    params = {}

print(generate_peer_id())

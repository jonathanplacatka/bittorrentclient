import torrent
import random
import requests
import bdecode

PORT = 6881

#20 bytes: 2 for client id, 4 for version number, remaining are random integers
def generate_peer_id():
    id = 'SY1000' 
    for k in range(0, 14):
        id += str(random.randint(0,9))
    return id

def get_peer_list():
    params = {
        'info_hash': torrent_file.info_hash,
        'peer_id': peer_id,
        'port': PORT,
        'uploaded': 0,
        'downloaded': 0,
        'left': torrent_file.length,
        'compact': 1,
        'event': 'started'
    }

    url = torrent_file.data['announce']

    response = requests.get(url, params)
    
    response_content = bdecode.decode(response.content)
    print(response_content)

def decode_peer_list():
   peers = b'\x8e\xa0k\x0e\x1a\xe1\xd43\x89\xb4\xc8\xd5\x18\xd9}i\xc0\x08'
   print(len(peers))

#torrent_file = torrent.Torrent('oz.torrent')
#peer_id = generate_peer_id()

#get_peer_list()
decode_peer_list()



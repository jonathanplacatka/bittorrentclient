import torrent
import random
import requests
import bdecode

PORT = 6881

#20 bytes: 2 for client id, 4 for version number, remaining are random integers
def generate_peer_id():
    id = 'PY1000' 
    for k in range(0, 14):
        id += str(random.randint(0,9))
    return id

def tracker_request():
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
    return bdecode.decode(response.content)

#TODO: check for compact vs non-compact peer list
def decode_compact_peer_list(peer_bytes):

    peer_list = []
    for x in range(0, len(peer_bytes), 6):
        ip = '.'.join(str(x) for x in peer_bytes[x:x+4]) #first 4 bytes are ip
        port = int.from_bytes(peer_bytes[x+4:x+6], byteorder='big') #last 2 bytes together are port
        peer_list.append('{}:{}'.format(ip, port))

    return peer_list



torrent_file = torrent.Torrent('oz.torrent')
peer_id = generate_peer_id()
tracker_response = tracker_request()

print(tracker_response)
print(decode_compact_peer_list(tracker_response['peers']))



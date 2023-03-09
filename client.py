import torrent
import random

import bdecode
import socket
import select

import requests
from requests import adapters

LISTEN_PORT = 7000

#20 bytes: 2 for client id, 4 for version number, remaining are random integers
def generate_peer_id():
    id = 'PY1000' 
    for k in range(0, 14):
        id += str(random.randint(0,9))
    return id

def tracker_request():
    request_params = {
        'info_hash': torrent_file.info_hash,
        'peer_id': peer_id,
        'port': LISTEN_PORT,
        'uploaded': 0,
        'downloaded': 0,
        'left': torrent_file.length,
        'compact': 1,
        'event': 'started'
    }

    url = torrent_file.data['announce']

    session = requests.Session()
    session.params = request_params
    #trackers sometimes respond with ConnectionResetError on valid requests, just retry
    retries = adapters.Retry(total=3, backoff_factor=1) 
    session.mount('http://', adapters.HTTPAdapter(max_retries=retries))
    response = session.get(url)

    return bdecode.decode(response.content)

#TODO: check for compact vs non-compact peer list (compact almost always used in practice)
def decode_compact_peer_list(peer_bytes):
    peer_list = []
    for x in range(0, len(peer_bytes), 6):
        ip = '.'.join(str(x) for x in peer_bytes[x:x+4]) #first 4 bytes are ip
        port = int.from_bytes(peer_bytes[x+4:x+6], byteorder='big') #last 2 bytes together are port
        peer_list.append((ip, port)) 

    return peer_list

def connect_peers():
    for peer in peer_list:   
        p_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        p_socket.setblocking(False)
        peer_sockets.append(p_socket)
        try:
            if p_socket.connect_ex(peer) == 0:
                p_socket.append(p_socket)
        except Exception as e:
            print('exception', e)

def send_handshake(peer_socket):
    HANDSHAKE = b'\x13BitTorrent protocol\x00\x00\x00\x00\x00\x00\x00\x00'
    msg = HANDSHAKE + torrent_file.info_hash + peer_id.encode()

    peer_socket.setblocking(True)
    peer_socket.sendall(msg)
    data = peer_socket.recv(1024)

    #print("received:", data)
    print("received handshake")

def run():
    while True:
        try:
            readable, writable, exceptions = select.select([], peer_sockets, [])

            for sock in writable:
                if sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0:
                    send_handshake(sock)
                    peer_sockets.remove(sock)
                    connected.append(sock)
                    print("{} connected: {}".format(len(connected), sock))
                else:
                    peer_sockets.remove(sock)
        except Exception as e:
            print('exception', e)

peer_sockets = []
connected = []

torrent_file = torrent.Torrent('bl.torrent')
peer_id = generate_peer_id()
tracker_response = tracker_request()
print(tracker_response)

peer_list = decode_compact_peer_list(tracker_response['peers'])
print(peer_list)
connect_peers()

run()







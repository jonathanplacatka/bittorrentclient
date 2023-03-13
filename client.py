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
        peer_list.append(Peer(ip, port)) 
    return peer_list

def connect_peers():
    for peer in peer_list:   
        p_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        p_socket.setblocking(False)
        errcode = p_socket.connect_ex(peer.address)
        
        if errcode == 115: #connection in progress     
            connecting.append(p_socket)
        elif errcode == 0: #connected
            connected.append(p_socket)

def send_handshake(peer_socket):
    HANDSHAKE = b'\x13BitTorrent protocol\x00\x00\x00\x00\x00\x00\x00\x00'
    msg = HANDSHAKE + torrent_file.info_hash + peer_id.encode()
    peer_socket.sendall(msg)
    #data = peer_socket.recv(1024)
    #print("received:", data)
    #print("received handshake")

def recieve_message(peer_socket):
    data = peer_socket.recv(1024)

    if data:
        #get peer object from list
        peer_ip = peer_socket.getpeername()
        peer = peer_list[peer_list.index(peer_ip)] 

        print("message receieved")
    else:
        connected.remove(peer_socket)

def run():
    while True:
        try:
            readable, writable, exceptions = select.select(connected, connecting, [])

            for sock in readable:
                    recieve_message(sock)

            for sock in writable:
                if sock in connecting:
                    if sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0:
                        sock.setblocking(True)
                        connecting.remove(sock)
                        connected.append(sock)
                        send_handshake(sock)
                        print("{} connected: {}".format(len(connected), sock))
                    else:
                        connecting.remove(sock)

        except Exception as e:
            print('exception', e)

class Peer:
    def __init__(self, ip, port):
        self.address = (ip, port)
    def __eq__(self, obj):
        return self.address == obj

peer_list = []

connecting = []
connected = []

torrent_file = torrent.Torrent('mint.torrent')
peer_id = generate_peer_id()
tracker_response = tracker_request()
print(tracker_response)

peer_list = decode_compact_peer_list(tracker_response['peers'])

for p in peer_list:
    print(p.address, end=', ')
print()

connect_peers()
run()







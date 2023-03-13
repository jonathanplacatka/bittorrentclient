import torrent
import random

import bdecode
import socket
import select

import requests
from requests import adapters

import bitstring


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


def recieve_message(data, peer_socket):
    #get peer object from list
    peer_ip = peer_socket.getpeername()
    peer = peer_list[peer_list.index(peer_ip)] 

    peer.buffer += data

    if peer.handshake == False:
        recieve_handshake(peer)
    elif len(peer.buffer) >= 5:
        msg_len = int.from_bytes(peer.buffer[0:4], byteorder='big')
        msg_id = peer.buffer[4]

        print("MSG: ", msg_len, msg_id)

        if len(peer.buffer) >= 4+msg_len:
            if msg_id == 0:
                pass
            elif msg_id == 1:
                recieve_unchoke(peer)
            elif msg_id == 5:
                recieve_bitfield(peer, msg_len)

            peer.buffer = peer.buffer[4+msg_len:]
            print("BUFFER", peer.buffer)

def recieve_handshake(peer):
    if len(peer.buffer) >= 68:
        if peer.buffer[0:20] == b'\x13BitTorrent protocol' and peer.buffer[28:48] == torrent_file.info_hash:
            print("RECEIVED: HANDSHAKE")
            print(peer.buffer[0:68])
            peer.handshake = True
            peer.buffer = peer.buffer[68:]
        else:
            print("invalid peer handshake, dropping connection")

#check if indices are correct for bitfield
def recieve_bitfield(peer, msg_len):
        
        print("BITFIELD LENGTH: ", msg_len-1)
        print("BUFFER", peer.buffer)

        bytes = peer.buffer[5:5+msg_len]

        print(len(bytes))

        peer.bitfield = bitstring.BitArray(bytes)

        print("RECIEVED: BITFIELD")
        print(len(peer.bitfield))
        print("ACTUAL ", peer.bitfield.bin.count('1'))

def recieve_unchoke(peer):
    peer.peer_choking = False
    print("RECIEVED: UNCHOKE")
    print(peer.buffer)

def send_message(peer_socket):
    #get peer object from list
    peer_ip = peer_socket.getpeername()
    peer = peer_list[peer_list.index(peer_ip)] 

    if peer.am_interested and not peer.peer_choking and not peer.request:
        send_request(peer_socket, 0, 0, 16384)
        peer.request = True
        
    elif not peer.am_interested: #check here if a peer has piece we are interested in
        print("SENDING INTERESTED")
        peer_socket.sendall(b'\x00\x00\x00\x01\x02')
        peer.am_interested = True

def send_handshake(peer_socket):
    print("SENT HANDSHAKE")
    HANDSHAKE = b'\x13BitTorrent protocol\x00\x00\x00\x00\x00\x00\x00\x00'
    msg = HANDSHAKE + torrent_file.info_hash + peer_id.encode()
    peer_socket.sendall(msg)

def send_request(peer_socket, index, begin, length):
    print("SENT REQUEST")
    msg = b'\x00\x00\x00\x0d\x06'
    msg += index.to_bytes(4, byteorder='big') 
    msg += begin.to_bytes(4, byteorder='big') 
    msg += length.to_bytes(4, byteorder='big')
    peer_socket.sendall(msg)

def run():
    while True:
        try:
            readable, writable, exceptions = select.select(connected, connecting + connected, [])

            for sock in readable:
                data = sock.recv(8192)
                if data:
                    recieve_message(data, sock)
                else:
                    connected.remove(sock)

            for sock in writable:
                if sock in connecting:
                    if sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0:
                        sock.setblocking(True)
                        connecting.remove(sock)
                        connected.append(sock)
                        send_handshake(sock)
                        print("{} connected: {}".format(len(connected), sock))
                        connecting.clear() #TESTING, REMOVE ME
                    else:
                        connecting.remove(sock)
                if sock in connected:
                    send_message(sock)
                    
        except Exception as e:
            print('exception', e)

class Peer:
    def __init__(self, ip, port):
        self.address = (ip, port)
        self.handshake = False
        self.buffer = b''
        self.bitfield = bitstring.BitArray(torrent_file.num_pieces)

        self.am_choking = True
        self.am_interested = False
        self.peer_choking = True
        self.peer_interested = False

        self.request = False

    def __eq__(self, obj):
        return self.address == obj


peer_list = []

connecting = []
connected = []

torrent_file = torrent.Torrent('mint.torrent')
peer_id = generate_peer_id()

tracker_response = tracker_request()
print(tracker_response)

print("NUM PIECES: " + str(torrent_file.num_pieces))


peer_list = decode_compact_peer_list(tracker_response['peers'])


for p in peer_list:
    print(p.address, end=', ')
print()

connect_peers()
run()
















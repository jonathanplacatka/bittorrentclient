import torrent
import messagehandler
import filehandler
import peer

import random

import bdecode
import socket
import select

import requests
from requests import adapters
import urllib.parse

import bitstring

LISTEN_PORT = 7000
BLOCK_SIZE = 16384

#20 bytes: 2 for client id, 4 for version number, remaining are random integers
def generate_peer_id():
    id = 'PY1000' 
    for k in range(0, 14):
        id += str(random.randint(0,9))
    return id

def tracker_request():
    request_params = {
        'info_hash': torrent.info_hash,
        'peer_id': peer_id,
        'port': LISTEN_PORT,
        'uploaded': 0,
        'downloaded': 0,
        'left': torrent.length,
        'compact': 1,
        'event': 'started'
    }

    encoded_params = urllib.parse.urlencode(request_params, quote_via=urllib.parse.quote)

    url = torrent.data['announce']

    session = requests.Session()

    #trackers sometimes respond with ConnectionResetError on valid requests, just retry
    retries = adapters.Retry(total=5, backoff_factor=1) 
    session.mount('http://', adapter=adapters.HTTPAdapter(max_retries=retries))
    response = session.get(url, params=encoded_params)

    return bdecode.decode(response.content)

#TODO: check for compact vs non-compact peer list (compact almost always used in practice)
def decode_compact_peer_list(peer_bytes):
    peer_list = []
    for x in range(0, len(peer_bytes), 6):
        ip = '.'.join(str(x) for x in peer_bytes[x:x+4]) #first 4 bytes are ip
        port = int.from_bytes(peer_bytes[x+4:x+6], byteorder='big') #last 2 bytes together are port
        peer_list.append(peer.Peer(ip, port, torrent)) 
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

def run():
    while True:
        try:
            readable, writable, exceptions = select.select(connected, connecting + connected, [])

            for sock in readable:
                data = sock.recv(BLOCK_SIZE)
                if data:
                   msg_handler.receive(data, sock, peer_list)
                else:
                    connected.remove(sock)

            for sock in writable:
                if sock in connecting:
                    if sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0:
                        sock.setblocking(True)
                        connecting.remove(sock)
                        connected.append(sock)
                        print("{} connected: {}".format(len(connected), sock))
                        #connecting.clear() #TESTING, REMOVE ME
                    
                    #else:
                        #connecting.remove(sock)
                if sock in connected:
                    msg_handler.send(sock, peer_list)
        
        except ValueError:
            connected.remove(sock)    
        except Exception as e:
            print('exception', e)

#TODO: create main/startup methods

peer_list = []
connecting = []
connected = []

torrent = torrent.Torrent('c.torrent')
peer_id = generate_peer_id()

print("FILENAME: ", torrent.data['info']['name'])
print("FILESIZE", torrent.length)
print("MULTIFILE: ", torrent.is_multi)
print("NUM PIECES: " + str(torrent.num_pieces))
print("PIECE SIZE: " + str(torrent.data['info']['piece length']))
print("BLOCK SIZE:",  str(BLOCK_SIZE))

tracker_response = tracker_request()

file_handler = filehandler.FileHandler(torrent)
msg_handler = messagehandler.MessageHandler(torrent, peer_id, file_handler)

peer_list = decode_compact_peer_list(tracker_response['peers'])

for p in peer_list:
    print(p.address, end=', ')
print()

connect_peers()
run()














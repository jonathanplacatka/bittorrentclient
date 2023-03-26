import torrent
import messagehandler
import filehandler

import random

import bdecode
import socket
import select

import requests
from requests import adapters
import urllib.parse

import bitstring
import math
import hashlib

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
        'info_hash': torrent_file.info_hash,
        'peer_id': peer_id,
        'port': LISTEN_PORT,
        'uploaded': 0,
        'downloaded': 0,
        'left': torrent_file.length,
        'compact': 1,
        'event': 'started'
    }

    encoded_params = urllib.parse.urlencode(request_params, quote_via=urllib.parse.quote)

    url = torrent_file.data['announce']

    session = requests.Session()

    #trackers sometimes respond with ConnectionResetError on valid requests, just retry
    retries = adapters.Retry(total=3, backoff_factor=1) 
    session.mount('http://', adapter=adapters.HTTPAdapter(max_retries=retries))
    response = session.get(url, params=encoded_params)

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

def receive_message(data, peer_socket):
    #get peer object from list
    peer_ip = peer_socket.getpeername()
    peer = peer_list[peer_list.index(peer_ip)] 

    peer.buffer += data

    if peer.handshake == False:
        receive_handshake(peer)
    elif len(peer.buffer) >= 5:
        msg_len = int.from_bytes(peer.buffer[0:4], byteorder='big')
        msg_id = peer.buffer[4]

        if len(peer.buffer) >= 4+msg_len:
            if msg_id == 0:
                pass
            elif msg_id == 1:
                receive_unchoke(peer)
            elif msg_id == 4:
                receive_have(peer)
            elif msg_id == 5:
                receive_bitfield(peer, msg_len)
            elif msg_id == 7:
                receive_piece(peer, msg_len)
            else:
                print("MSG: ", msg_len, msg_id)

            peer.buffer = peer.buffer[4+msg_len:]

def receive_piece(peer, msg_len):

    index = int.from_bytes(peer.buffer[5:9], byteorder='big')
    begin = int.from_bytes(peer.buffer[9:13], byteorder='big')
    block = peer.buffer[13:13+msg_len]

    #print("RECIEVED - PIECE:{} BLOCK:{}".format(index, int(begin/BLOCK_SIZE)))

    byte_offset =  index*torrent_file.data['info']['piece length'] + begin
    fp_out.seek(byte_offset, 0)
    fp_out.write(block)

    blocks_received[index][int(begin/BLOCK_SIZE)] = True
    peer.request = False

    validate_piece(index)

def validate_piece(piece_index):
    if blocks_received[piece_index].all(True):
        hash_offset = piece_index*20
        piece_hash = torrent_file.data['info']['pieces'][hash_offset:hash_offset+20]

        fp_out.seek(piece_index*torrent_file.data['info']['piece length'], 0)
        piece = fp_out.read(torrent_file.data['info']['piece length'])

        if hashlib.sha1(piece).digest() == piece_hash:
            print("PIECE {} VALID".format(piece_index))
        else: #invalid piece, re-request all blocks
            print("INVALID PIECE")
            num_blocks = blocks_per_piece 
            
            if piece_index == torrent_file.num_pieces-1:
                num_blocks = blocks_per_final_piece

            blocks_requested[piece_index] = bitstring.BitArray(num_blocks)
            blocks_received[piece_index] = bitstring.BitArray(num_blocks)

def receive_have(peer):
    print("RECIEVED HAVE: INDEX {}".format(index))
    index = int.from_bytes(peer.buffer[5:9], byteorder='big')
    peer.bitfield[index] = True


def receive_handshake(peer):
    if len(peer.buffer) >= 68:
        if peer.buffer[0:20] == b'\x13BitTorrent protocol' and peer.buffer[28:48] == torrent_file.info_hash:
            print("RECEIVED: HANDSHAKE")
            #print(peer.buffer[0:68])
            peer.handshake = True
            peer.buffer = peer.buffer[68:]
        else:
            print("invalid peer handshake, dropping connection")

def receive_bitfield(peer, msg_len):
    bytes = peer.buffer[5:5+msg_len]
    peer.bitfield = bitstring.BitArray(bytes)
    print("RECEIVED: BITFIELD")
    #print(peer.bitfield.bin)

def receive_unchoke(peer):
    peer.peer_choking = False
    print("RECEIVED: UNCHOKE")

def send_message(peer_socket):
    #get peer object from list
    peer_ip = peer_socket.getpeername()
    peer = peer_list[peer_list.index(peer_ip)] 

    if peer.am_interested and not peer.peer_choking and not peer.request: # and not peer.request
        send_request(peer, peer_socket)
        peer.request = True
        
    elif not peer.am_interested: #TODO: check if peer has piece we are interested in
        print("SENDING INTERESTED")
        peer_socket.sendall(b'\x00\x00\x00\x01\x02')
        peer.am_interested = True

def send_handshake(peer_socket):
    print("SENT HANDSHAKE")
    HANDSHAKE = b'\x13BitTorrent protocol\x00\x00\x00\x00\x00\x00\x00\x00'
    msg = HANDSHAKE + torrent_file.info_hash + peer_id.encode()
    peer_socket.sendall(msg)

def send_request(peer, peer_socket):
    request_params = select_block(peer)

    if len(request_params) > 0 and peer.request == False: 

        piece_index = request_params[0]
        block_index = request_params[1]

        length = BLOCK_SIZE

        #final block may have different size
        if piece_index == torrent_file.num_pieces-1 and block_index == blocks_per_final_piece-1:
            length = final_piece_size - (blocks_per_final_piece-1)*BLOCK_SIZE

        peer.request = True 

        #print("SENT REQUEST - PIECE:{} BLOCK:{}".format(request_params[0], request_params[1]))

        begin = block_index*BLOCK_SIZE

        msg = b'\x00\x00\x00\x0d\x06'
        msg += piece_index.to_bytes(4, byteorder='big') 
        msg += begin.to_bytes(4, byteorder='big') 
        msg += length.to_bytes(4, byteorder='big')

        peer_socket.sendall(msg)
    
def select_block(peer):

    for piece_index in range(torrent_file.num_pieces): 

        find_block = blocks_requested[piece_index].find('0b0')
    
        #check if we are missing a block and if peer has this piece
        if len(find_block) > 0 and peer.bitfield[piece_index] == True:
            block_index = find_block[0]
            blocks_requested[piece_index][block_index] = True
            return (piece_index, block_index)
        
    return ()

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
                    else:
                        connecting.remove(sock)
                if sock in connected:
                    msg_handler.send(sock, peer_list)
        
        except ValueError:
            connected.remove(sock)    
        except Exception as e:
            print('exception', e)


class Peer:
    def __init__(self, ip, port):
        self.address = (ip, port)

        self.sent_handshake = False
        self.received_handshake = False

        self.buffer = b''
        self.bitfield = bitstring.BitArray(torrent_file.num_pieces)

        self.am_choking = True
        self.am_interested = False
        self.peer_choking = True
        self.peer_interested = False

        self.request = False


    def __eq__(self, obj):
        return self.address == obj

#TODO: create main/startup methods

peer_list = []
connecting = []
connected = []

torrent_file = torrent.Torrent('mint.torrent')
peer_id = generate_peer_id()

open(torrent_file.data['info']['name'], 'a+').close() #create file if it doesn't exist

fp_out = open(torrent_file.data['info']['name'], 'r+b') #open file for reading and writing

print("FILENAME: ", torrent_file.data['info']['name'])
print("FILESIZE", torrent_file.length)
print("MULTIFILE: ", torrent_file.is_multi)
print("NUM PIECES: " + str(torrent_file.num_pieces))
print("PIECE SIZE: " + str(torrent_file.data['info']['piece length']))
print("BLOCK SIZE:",  str(BLOCK_SIZE))

tracker_response = tracker_request()
blocks_per_piece = math.ceil(torrent_file.data['info']['piece length'] / BLOCK_SIZE)

final_piece_size = torrent_file.length - (torrent_file.num_pieces-1)*torrent_file.data['info']['piece length']
blocks_per_final_piece = math.ceil(final_piece_size / BLOCK_SIZE)

blocks_requested = []
blocks_received = []


for i in range(torrent_file.num_pieces):
    num_blocks = blocks_per_piece
    #last piece may have less blocks
    if i == torrent_file.num_pieces-1:
        num_blocks = blocks_per_final_piece

    blocks_requested.append(bitstring.BitArray(num_blocks))
    blocks_received.append(bitstring.BitArray(num_blocks))

file_handler = filehandler.FileHandler(torrent_file)
msg_handler = messagehandler.MessageHandler(torrent_file, peer_id, file_handler)

peer_list = decode_compact_peer_list(tracker_response['peers'])

for p in peer_list:
    print(p.address, end=', ')
print()

connect_peers()

print(final_piece_size/BLOCK_SIZE)
print(len(blocks_requested[torrent_file.num_pieces-1]))

run()














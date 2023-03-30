import bdecode
import torrent
import messagehandler
import filehandler
import peer
import const

import random
import socket
import select
import errno
import sys

import requests
from requests import adapters
import urllib.parse

class Client:

    def __init__(self, filename):
        self.torrent = torrent.Torrent(filename)

        self.peer_id = self.generate_peer_id()
        self.peer_list = []
        
        self.file_handler = filehandler.FileHandler(self.torrent)
        self.msg_handler = messagehandler.MessageHandler(self.torrent, self.peer_id, self.file_handler) 
    
    def run(self):
        connecting = []
        connected = []

        self.print_torrent_info()

        print("Sending Tracker Request...")

        tracker_response = self.tracker_request()

        print("Response Received!")

        if isinstance(tracker_response['peers'], list):
            self.peer_list = self.read_peer_list(tracker_response['peers'])
        else:
            self.peer_list = self.read_compact_peer_list(tracker_response['peers'])

        print('# of Peers: {}\n'.format(len(self.peer_list)))
    
        self.connect_peers(connecting, connected)
        self.process(connecting, connected)

    def tracker_request(self):
        request_params = {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'port': const.LISTEN_PORT,
            'uploaded': 0,
            'downloaded': 0,
            'left': self.torrent.length,
            'compact': 1,
            'event': 'started'
        }

        encoded_params = urllib.parse.urlencode(request_params, quote_via=urllib.parse.quote)

        url = self.torrent.data['announce']
        session = requests.Session()

        #trackers sometimes respond with ConnectionResetError on valid requests, just retry
        try:
            retries = adapters.Retry(total=5, backoff_factor=0.5) 
            session.mount('http://', adapter=adapters.HTTPAdapter(max_retries=retries))
            response = session.get(url, params=encoded_params)
        except Exception as e:
            print(e)
            print('Tracker Unavailable: Try again or use a different torrent file')
            exit()

        return bdecode.decode(response.content)

    def connect_peers(self, connecting, connected):
        for peer in self.peer_list:   
            p_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            p_socket.setblocking(False)
            errcode = p_socket.connect_ex(peer.address)
            
            if errcode == errno.EINPROGRESS or errcode == errno.EWOULDBLOCK: #connection in progress        
                connecting.append(p_socket)
            elif errcode == 0: #connected
                connected.append(p_socket)

    def process(self, connecting, connected):
        while True:
            try:
                readable, writable, exceptions = select.select(connected, connecting + connected, [])

                for sock in readable:
                    data = sock.recv(const.BLOCK_SIZE)
                    if data:
                        self.msg_handler.receive(data, self.get_peer_from_socket(sock))
                    else:
                        #peer closed connection
                        self.drop_connection(sock, connected)
                    
                for sock in writable:
                    if sock in connecting:
                        if sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0:
                            sock.setblocking(True)
                            connecting.remove(sock)
                            connected.append(sock)
                            print("{} connected: {}".format(len(connected), sock.getpeername()))
                            #connecting.clear() #TESTING, REMOVE ME
                        else:
                            connecting.remove(sock)
                        
                    if sock in connected:
                        try:
                            self.msg_handler.send(self.get_peer_from_socket(sock), sock)
                        except Exception as e:
                            #failed to send, drop connection
                            self.drop_connection(sock, connected)

            except ValueError:
                connected.remove(sock)  
            except Exception as e:
                print('exception:', e)

    def read_compact_peer_list(self, peer_bytes):
        peer_list = []
        for x in range(0, len(peer_bytes), 6):
            ip = '.'.join(str(x) for x in peer_bytes[x:x+4]) #first 4 bytes are ip
            port = int.from_bytes(peer_bytes[x+4:x+6], byteorder='big') #last 2 bytes together are port
            peer_list.append(peer.Peer(ip, port, self.torrent)) 
        return peer_list

    def read_peer_list(self, peers):
        peer_list = []
        for dict in peers:
            ip = dict[b'ip'].decode()
            port = dict[b'port']
            peer_list.append(peer.Peer(ip, port, self.torrent))
        return peer_list

    def drop_connection(self, peer_socket, connected):
        connected.remove(peer_socket)
        peer = self.get_peer_from_socket(peer_socket)
        self.msg_handler.reset_pieces(peer)

    def get_peer_from_socket(self, socket):
        peer_ip = socket.getpeername()
        index = self.peer_list.index(peer_ip)
        return self.peer_list[index]
    
    #20 bytes: 2 for client id, 4 for version number, remaining are random integers
    def generate_peer_id(self):
        id = 'PY1000' 
        for k in range(0, 14):
            id += str(random.randint(0,9))
        return id
    
    def print_torrent_info(self):
        print('Filename: {}\nSize: {}\nMultifile: {}\n# of Pieces: {}\n'.format(self.torrent.data['info']['name'], self.torrent.length, self.torrent.is_multi, self.torrent.num_pieces))

def main():
    if len(sys.argv) == 2:
        c = Client(sys.argv[1])
        c.run()
    else:
        print("Invalid Arguments! Use: python3 client [torrent]")

if __name__ == '__main__':
    main()






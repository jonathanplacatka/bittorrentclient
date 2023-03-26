import bitstring

BLOCK_SIZE = 16384

class MessageHandler:

    def __init__(self, torrent_file, peer_id, file_handler):
        self.torrent_file = torrent_file
        self.peer_id = peer_id
        self.file_handler = file_handler

    def receive(self, data, peer_socket, peer_list):

        peer = self.get_peer_from_socket(peer_socket, peer_list)
        peer.buffer += data

        if peer.received_handshake == False:
            self.receive_handshake(peer, peer_list)
        elif len(peer.buffer) >= 5:
            msg_len = int.from_bytes(peer.buffer[0:4], byteorder='big')
            msg_id = peer.buffer[4]

            if len(peer.buffer) >= 4+msg_len:
                if msg_id == 0:
                    self.receive_choke(peer)
                elif msg_id == 1:
                    self.receive_unchoke(peer)
                elif msg_id == 4:
                    self.receive_have(peer)
                elif msg_id == 5:
                    self.receive_bitfield(peer, msg_len)
                elif msg_id == 7:
                    self.receive_piece(peer, msg_len)
                else:
                    print("UNIMPLEMENTED MESSAGE: ", msg_len, msg_id)

                peer.buffer = peer.buffer[4+msg_len:] #clear message from buffer

    def send(self, peer_socket, peer_list):
        peer = self.get_peer_from_socket(peer_socket, peer_list)

        if peer.sent_handshake == False:
            self.send_handshake(peer_socket)
            peer.sent_handshake = True

    def receive_handshake(self, peer, peer_list):
        if len(peer.buffer) >= 68:
            if peer.buffer[0:20] == b'\x13BitTorrent protocol' and peer.buffer[28:48] == self.torrent_file.info_hash:
                print("RECEIVED: HANDSHAKE")
                peer.received_handshake = True
            else: #invalid handshake, drop connection
                peer_list.remove(peer)
                raise ValueError("Invalid Handshake Message")
            
        peer.buffer = peer.buffer[68:]

    def receive_unchoke(self, peer):
        print("RECEIVED: UNCHOKE")
        peer.peer_choking = False

    def receive_choke(self, peer):
        print("RECEIVED: CHOKE")
        peer.peer_choking = True

    def receive_have(self, peer):
        print("RECIEVED HAVE: INDEX {}".format(index))
        index = int.from_bytes(peer.buffer[5:9], byteorder='big')
        peer.bitfield[index] = True

    def receive_bitfield(self, peer, msg_len):
        print("RECEIVED: BITFIELD")
        bytes = peer.buffer[5:5+msg_len]
        peer.bitfield = bitstring.BitArray(bytes)

    def receive_piece(self, peer, msg_len):
        print("RECIEVED - PIECE:{} BLOCK:{}".format(index, int(begin/BLOCK_SIZE)))

        index = int.from_bytes(peer.buffer[5:9], byteorder='big')
        begin = int.from_bytes(peer.buffer[9:13], byteorder='big')
        block = peer.buffer[13:13+msg_len]

        self.file_handler.write(index, begin, block)
        peer.request = False

    def send_handshake(self, peer_socket):
        print("SENT HANDSHAKE")
        HANDSHAKE = b'\x13BitTorrent protocol\x00\x00\x00\x00\x00\x00\x00\x00'
        msg = HANDSHAKE + self.torrent_file.info_hash + self.peer_id.encode()
        peer_socket.sendall(msg)

    def get_peer_from_socket(self, socket, peer_list):
        peer_ip = socket.getpeername()
        index = peer_list.index(peer_ip)
        return peer_list[index]
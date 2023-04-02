import const

import bitstring
from collections import deque

class MessageHandler:

    def __init__(self, torrent, peer_id, file_handler):
        self.torrent = torrent
        self.peer_id = peer_id
        self.file_handler = file_handler
        self.rqueue = self.init_queue()

    def init_queue(self):
        queue = deque()

        for i in range(self.torrent.num_pieces):
            num_blocks = self.torrent.blocks_per_piece
            if i == self.torrent.num_pieces-1: 
                num_blocks = self.torrent.blocks_per_final_piece
            
            for j in range(num_blocks):
                queue.append((i, j))

        return queue

    def receive(self, data, peer):
        peer.buffer += data

        if peer.received_handshake == False:
            self.receive_handshake(peer)
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
                    self.log("RECEIVED UNIMPLEMENTED MSG: " + msg_id)

                peer.buffer = peer.buffer[4+msg_len:] #clear message from buffer

    def receive_handshake(self, peer):
        if len(peer.buffer) >= 68:
            if peer.buffer[0:20] == b'\x13BitTorrent protocol' and peer.buffer[28:48] == self.torrent.info_hash:
                self.log("RECEIVED: HANDSHAKE")
                peer.received_handshake = True
            
        peer.buffer = peer.buffer[68:]

    def receive_unchoke(self, peer):
        self.log("RECEIVED: UNCHOKE")
        peer.peer_choking = False

    def receive_choke(self, peer):
        self.log("RECEIVED: CHOKE")
        peer.peer_choking = True
        self.reset_pieces(peer)

    def receive_have(self, peer):
        index = int.from_bytes(peer.buffer[5:9], byteorder='big')
        peer.bitfield[index] = True
        self.log("RECIEVED HAVE - INDEX:{}".format(index))

    def receive_bitfield(self, peer, msg_len):
        self.log("RECEIVED: BITFIELD")
        bytes = peer.buffer[5:5+msg_len-1]
        peer.bitfield = bitstring.BitArray(bytes)

    def receive_piece(self, peer, msg_len):
        index = int.from_bytes(peer.buffer[5:9], byteorder='big')
        begin = int.from_bytes(peer.buffer[9:13], byteorder='big')
        block = peer.buffer[13:13+msg_len-9]

        block_index = int(begin/const.BLOCK_SIZE)

        self.file_handler.write(index, begin, block)
        peer.requested.remove((index, block_index))

        self.log("RECIEVED - PIECE:{} BLOCK:{}".format(index, block_index))

        if self.file_handler.bitfield[0:self.torrent.num_pieces].all(True):
            print("Download Complete.")
            exit()

    def send(self, peer, peer_socket):
        if peer.sent_handshake == False:
            self.send_handshake(peer, peer_socket)
        elif not peer.am_interested and self.file_handler.check_interest(peer): 
            self.send_interested(peer, peer_socket)
        elif peer.am_interested and not peer.peer_choking and len(peer.requested) == 0:
            self.send_request(peer, peer_socket)

    def send_handshake(self, peer, peer_socket):
        self.log("SENT HANDSHAKE")
        HANDSHAKE = b'\x13BitTorrent protocol\x00\x00\x00\x00\x00\x00\x00\x00'
        msg = HANDSHAKE + self.torrent.info_hash + self.peer_id.encode()
        peer_socket.sendall(msg)
        peer.sent_handshake = True

    def send_request(self, peer, peer_socket):
        msg = b''

        for i in range(0, const.BLOCKS_PER_REQUEST): 
            try:
                indices = self.rqueue.popleft()

                piece_index = indices[0]
                block_index = indices[1]

                begin = block_index*const.BLOCK_SIZE

                length = const.BLOCK_SIZE

                #final block may have different size
                if piece_index == self.torrent.num_pieces-1 and block_index == self.torrent.blocks_per_final_piece-1:
                    length = self.torrent.final_piece_size - (self.torrent.blocks_per_final_piece-1)*const.BLOCK_SIZE

                peer.requested.append(indices)

                msg += b'\x00\x00\x00\x0d\x06'
                msg += piece_index.to_bytes(4, byteorder='big') 
                msg += begin.to_bytes(4, byteorder='big') 
                msg += length.to_bytes(4, byteorder='big')

                self.log("SENT REQUEST - PIECE:{} BLOCK:{}".format(piece_index, block_index))

            except IndexError:
                pass

        if len(msg) > 0:
            peer_socket.sendall(msg)

    def send_interested(self, peer, peer_socket):
        self.log("SENDING INTERESTED")
        peer_socket.sendall(b'\x00\x00\x00\x01\x02')
        peer.am_interested = True

    def reset_pieces(self, peer):
        #re-request outstanding pieces
        self.rqueue.extendleft(peer.requested)

    def log(self, msg):
        if const.LOG_ALL_MESSAGES: 
            print(msg)




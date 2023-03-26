import bitstring

BLOCK_SIZE = 16384
BLOCKS_PER_REQUEST = 6

class MessageHandler:

    def __init__(self, torrent, peer_id, file_handler):
        self.torrent = torrent
        self.peer_id = peer_id
        self.file_handler = file_handler

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
                    print("Unimplemented Message: ", msg_len, msg_id)

                peer.buffer = peer.buffer[4+msg_len:] #clear message from buffer

    def receive_handshake(self, peer):
        if len(peer.buffer) >= 68:
            if peer.buffer[0:20] == b'\x13BitTorrent protocol' and peer.buffer[28:48] == self.torrent.info_hash:
                #print("RECEIVED: HANDSHAKE")
                peer.received_handshake = True
            else: #invalid handshake, drop connection
                raise ValueError("Invalid Handshake Message")
            
        peer.buffer = peer.buffer[68:]

    def receive_unchoke(self, peer):
        #print("RECEIVED: UNCHOKE")
        peer.peer_choking = False

    def receive_choke(self, peer):
        #print("RECEIVED: CHOKE")
        peer.peer_choking = True

    def receive_have(self, peer):
        index = int.from_bytes(peer.buffer[5:9], byteorder='big')
        print("RECIEVED HAVE: INDEX {}".format(index))
        peer.bitfield[index] = True

    def receive_bitfield(self, peer, msg_len):
        print("RECEIVED: BITFIELD")
        bytes = peer.buffer[5:5+msg_len-1]
        peer.bitfield = bitstring.BitArray(bytes)

    def receive_piece(self, peer, msg_len):
        index = int.from_bytes(peer.buffer[5:9], byteorder='big')
        begin = int.from_bytes(peer.buffer[9:13], byteorder='big')
        block = peer.buffer[13:13+msg_len-9]

        block_index = int(begin/BLOCK_SIZE)

        #print("RECIEVED - PIECE:{} BLOCK:{}".format(index, block_index))

        self.file_handler.write(index, begin, block)
        peer.requested.remove((index, block_index))

        if self.file_handler.bitfield[0:self.torrent.num_pieces].all(True):
            print("download complete!")
            exit()

    def send_handshake(self, peer, peer_socket):
        #print("SENT HANDSHAKE")
        HANDSHAKE = b'\x13BitTorrent protocol\x00\x00\x00\x00\x00\x00\x00\x00'
        msg = HANDSHAKE + self.torrent.info_hash + self.peer_id.encode()
        peer_socket.sendall(msg)
        peer.sent_handshake = True

    def send(self, peer, peer_socket):
        if peer.sent_handshake == False:
            self.send_handshake(peer, peer_socket)
        elif not peer.am_interested and self.file_handler.check_interest(peer): 
            self.send_interested(peer, peer_socket)
        elif peer.am_interested and not peer.peer_choking and len(peer.requested) == 0:
            self.send_request(peer, peer_socket)

    def send_request(self, peer, peer_socket):
        msg = b''

        for i in range(0, BLOCKS_PER_REQUEST):
            request_params = self.file_handler.select_block(peer)

            #print("SENT REQUEST - PIECE:{} BLOCK:{}".format(request_params[0], request_params[1]))
            
            if len(request_params) > 0:
                piece_index = request_params[0]
                block_index = request_params[1]

                length = BLOCK_SIZE
                begin = block_index*BLOCK_SIZE

                #final block may have different size
                if piece_index == self.torrent.num_pieces-1 and block_index == self.torrent.blocks_per_final_piece-1:
                    length = self.torrent.final_piece_size - (self.torrent.blocks_per_final_piece-1)*BLOCK_SIZE

                peer.requested.append((piece_index, block_index))
            
                msg += b'\x00\x00\x00\x0d\x06'
                msg += piece_index.to_bytes(4, byteorder='big') 
                msg += begin.to_bytes(4, byteorder='big') 
                msg += length.to_bytes(4, byteorder='big')

        peer_socket.sendall(msg)

    def send_interested(self, peer, peer_socket):
        #print("SENDING INTERESTED")
        peer_socket.sendall(b'\x00\x00\x00\x01\x02')
        peer.am_interested = True

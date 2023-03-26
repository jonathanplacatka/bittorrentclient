
import bitstring

class Peer:
    def __init__(self, ip, port, torrent):
        self.address = (ip, port)
   
        self.sent_handshake = False
        self.received_handshake = False

        self.buffer = b''

        #evil bit hack - rounds up to next multiple of 8
        self.bitfield = bitstring.BitArray(((torrent.num_pieces + 7) >> 3) << 3)

        self.am_choking = True
        self.am_interested = False
        self.peer_choking = True
        self.peer_interested = False

        self.requested = []

    def __eq__(self, obj):
        return self.address == obj
    

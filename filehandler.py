import bitstring
import hashlib

BLOCK_SIZE = 16384

class FileHandler:

    def __init__(self, torrent):

        self.torrent = torrent

        self.bitfield = bitstring.BitArray(((torrent.num_pieces + 7) >> 3) << 3)
        self.blocks_requested = []
        self.blocks_received = []
        
        open(torrent.data['info']['name'], 'a+').close() #create file if it doesn't exist
        self.fp_out = open(torrent.data['info']['name'], 'r+b') #open file for reading and writing
    
        #initialize block bitstrings
        for i in range(torrent.num_pieces):
            num_blocks = torrent.blocks_per_piece

            if i == torrent.num_pieces-1:  #last piece may have less blocks
                num_blocks = torrent.blocks_per_final_piece

            self.blocks_requested.append(bitstring.BitArray(num_blocks))
            self.blocks_received.append(bitstring.BitArray(num_blocks))

    def write(self, piece_index, begin, data):

        byte_offset = piece_index*self.torrent.data['info']['piece length'] + begin

        self.fp_out.seek(byte_offset, 0)
        self.fp_out.write(data)

        self.blocks_received[piece_index][int(begin/BLOCK_SIZE)] = True

        self.validate_piece(piece_index)

    def validate_piece(self, piece_index):
        if self.blocks_received[piece_index].all(True):

            self.bitfield[piece_index] = True

            hash_offset = piece_index*20
            piece_hash = self.torrent.data['info']['pieces'][hash_offset:hash_offset+20]

            self.fp_out.seek(piece_index*self.torrent.data['info']['piece length'], 0)
            piece = self.fp_out.read(self.torrent.data['info']['piece length'])

            if hashlib.sha1(piece).digest() == piece_hash:
                print("PIECE {} VALID".format(piece_index))
                print(self.bitfield.bin)
            else: #invalid piece, re-request all blocks

                self.bitfield[piece_index] = False

                print("INVALID PIECE")
                num_blocks = self.torrent.blocks_per_piece 
                
                if piece_index == self.torrent.num_pieces-1:
                    num_blocks = self.torrent.blocks_per_final_piece
                
                self.blocks_requested[piece_index] = bitstring.BitArray(num_blocks)
                self.blocks_received[piece_index] = bitstring.BitArray(num_blocks)

    def check_interest(self, peer):
        #resulting bitfield represents pieces we don't have, but peer does have
        return not ((self.bitfield ^ peer.bitfield) & peer.bitfield).all(False)
    
    def select_block(self, peer):

        find_pieces = ((self.bitfield ^ peer.bitfield) & peer.bitfield).findall('0b1')
        
        for piece_index in find_pieces:

            find_block = self.blocks_requested[piece_index].find('0b0')

            if len(find_block) > 0:
                block_index = find_block[0]
                self.blocks_requested[piece_index][block_index] = True
                return (piece_index, block_index)

        return ()
    
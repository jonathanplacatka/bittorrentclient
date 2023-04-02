import const

import bitstring
import hashlib
import bisect
import os

class FileHandler:

    def __init__(self, torrent):

        self.torrent = torrent

        #keep track of requested/recieved blocks
        self.blocks_requested = []
        self.blocks_received = []
        
        #round up to next multiple of 8
        self.bitfield = bitstring.BitArray(((torrent.num_pieces + 7) >> 3) << 3)

        self.fp_list = []

        #create output files
        if torrent.is_multi:
            for file in torrent.data['info']['files']:
                path = '{}/{}'.format(torrent.data['info']['name'], '/'.join(file['path']))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                self.fp_list.append(open(path, 'wb+'))
        else:
            self.fp_out = open(torrent.data['info']['name'], 'wb+')
        
        #initialize block bitstrings
        for i in range(torrent.num_pieces):
            num_blocks = torrent.blocks_per_piece

            if i == torrent.num_pieces-1:  #last piece may have less blocks
                num_blocks = torrent.blocks_per_final_piece

            self.blocks_requested.append(bitstring.BitArray(num_blocks))
            self.blocks_received.append(bitstring.BitArray(num_blocks))

    def write(self, piece_index, begin, data):
        byte_offset = piece_index*self.torrent.data['info']['piece length'] + begin

        if self.torrent.is_multi:
            self.write_multi(byte_offset, data)
        else:
            self.fp_out.seek(byte_offset, 0)
            self.fp_out.write(data)

        self.blocks_received[piece_index][int(begin/const.BLOCK_SIZE)] = True
        self.validate_piece(piece_index)

    def validate_piece(self, piece_index):
        if self.blocks_received[piece_index].all(True) and self.bitfield[piece_index] == False:
            self.bitfield[piece_index] = True

            hash_offset = piece_index*20
            piece_hash = self.torrent.data['info']['pieces'][hash_offset:hash_offset+20]

            size = self.torrent.data['info']['piece length']
            if piece_index == self.torrent.num_pieces-1:
                size = self.torrent.final_piece_size
            byte_offset = piece_index*self.torrent.data['info']['piece length']

            #read piece from file
            if self.torrent.is_multi:
                piece = self.read_multi(byte_offset, size)
            else:
                self.fp_out.seek(byte_offset, 0)
                piece = self.fp_out.read(size)
            
            #check piece against hash from torrent file
            if hashlib.sha1(piece).digest() == piece_hash:
                print("RECEIVED PIECE {}".format(piece_index+1))
                print(self.bitfield.bin[0:self.torrent.num_pieces])
            else: #invalid piece, re-request all blocks
                print("INVALID PIECE")

                self.bitfield[piece_index] = False

                num_blocks = self.torrent.blocks_per_piece 
                
                if piece_index == self.torrent.num_pieces-1:
                    num_blocks = self.torrent.blocks_per_final_piece
                
                self.blocks_requested[piece_index] = bitstring.BitArray(num_blocks)
                self.blocks_received[piece_index] = bitstring.BitArray(num_blocks)

    def check_interest(self, peer):
        #resulting bitfield represents pieces we don't have, but peer does have
        return not ((self.bitfield ^ peer.bitfield) & peer.bitfield).all(False)
    
    #write block across multiple files
    def write_multi(self, byte_offset, data):
        files = self.torrent.data['info']['files']
        file_index = bisect.bisect(self.torrent.file_offsets, byte_offset)-1
        bytes_written = 0

        while bytes_written < len(data):
            #amount left to write in this file
            file_bytes = self.torrent.file_offsets[file_index] + files[file_index]['length'] - byte_offset

            amount = min(file_bytes, len(data)-bytes_written)

            self.fp_list[file_index].seek(byte_offset-self.torrent.file_offsets[file_index], 0)
            self.fp_list[file_index].write(data[bytes_written:bytes_written+amount])

            byte_offset += amount
            bytes_written += amount
            file_index += 1

    #read block across multiple files
    def read_multi(self, byte_offset, size):
        files = self.torrent.data['info']['files']      
        file_index = bisect.bisect(self.torrent.file_offsets, byte_offset)-1
        bytes_read = 0
        data = b''
        
        while bytes_read < size:

            file_bytes = self.torrent.file_offsets[file_index] + files[file_index]['length'] - byte_offset
            amount = min(file_bytes, size-bytes_read)

            self.fp_list[file_index].seek(byte_offset-self.torrent.file_offsets[file_index], 0)
            data += self.fp_list[file_index].read(amount)
            
            byte_offset += amount
            bytes_read += amount
            file_index += 1

        return data


    
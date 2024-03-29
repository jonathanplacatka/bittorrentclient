import const

import bencodepy
import hashlib
import bdecode
import math

class Torrent:
    def __init__(self, filename):
        self.data = {}
        self.length = 0
        self.info_hash = None

        self.num_pieces = 0
        self.blocks_per_piece = 0
        self.blocks_per_final_piece = 0
        self.final_piece_size = 0

        self.is_multi = False
        self.file_offsets = []

        self.read_torrent(filename)
    
    def read_torrent(self, filename):
        try:
            with open(filename, 'rb') as fp:
                data_bencoded = fp.read()
            self.data = bdecode.decode(data_bencoded)

            #get SHA1 hash of bencoded info dictionary
            info_bencoded = bencodepy.encode(self.data['info'])
            self.info_hash = hashlib.sha1(info_bencoded).digest()

            #calculate multifile length and offsets
            if('files' in self.data['info']):
                self.is_multi = True
                total = 0
                for file in self.data['info']['files']:
                    self.file_offsets.append(total)
                    total += file['length']

                self.length = total
            else:
                self.length = self.data['info']['length']

            #calculate piece info
            self.num_pieces = math.ceil(self.length / self.data['info']['piece length'])
            self.blocks_per_piece = math.ceil(self.data['info']['piece length'] / const.BLOCK_SIZE)

            self.final_piece_size = self.length - (self.num_pieces-1)*self.data['info']['piece length']
            self.blocks_per_final_piece = math.ceil(self.final_piece_size / const.BLOCK_SIZE)
        except Exception as e:
            print(e, '\nUnsupported File: Use a different torrent file')
            exit()

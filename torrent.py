import bencodepy
import hashlib
import bdecode
import math

BLOCK_SIZE = 16384 #TODO: make common location for constants?

#class representing a torrent file
class Torrent:
    def __init__(self, filename):
        self.data = {}
        self.length = 0
        self.num_pieces = 0
        self.blocks_per_piece = 0
        self.blocks_per_final_piece = 0
        self.is_multi = False
        self.info_hash = None

        self.read_torrent(filename)
    
    def read_torrent(self, filename):
        with open(filename, 'rb') as fp:
            data_bencoded = fp.read()

        self.data = bdecode.decode(data_bencoded)
        
        #get SHA1 hash of bencoded info dictionary
        info_bencoded = bencodepy.encode(self.data['info'])
        self.info_hash = hashlib.sha1(info_bencoded).digest()

        if('files' in self.data['info']):
            self.is_multi = True
            self.length = self.get_multifile_length()
        else:
            self.length = self.data['info']['length']

        self.num_pieces = math.ceil(self.length / self.data['info']['piece length'])
        self.blocks_per_piece = math.ceil(self.data['info']['piece length'] / BLOCK_SIZE)
        
        final_piece_size = self.length - (self.num_pieces-1)*self.data['info']['piece length']
        self.blocks_per_final_piece = math.ceil(final_piece_size / BLOCK_SIZE)


    def get_multifile_length(self):
        total = 0
        for file in self.data['info']['files']:
            total += file['length']
        return total

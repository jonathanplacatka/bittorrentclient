import bencodepy
import hashlib
import bdecode
import math

#class representing a torrent file
class Torrent:
    def __init__(self, filename):
        self.data = {}
        self.length = 0
        self.num_pieces = 0
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
            self.length = self.get_total_length()
        else:
            self.length = self.data['info']['length']

        self.num_pieces = math.ceil(self.length / self.data['info']['piece length'])

        
    def get_total_length(self):
        total = 0
        for file in self.data['info']['files']:
            total += file['length']
        return total

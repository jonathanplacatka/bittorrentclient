import bencodepy
import hashlib

#class representing a torrent file
class Torrent:
    def __init__(self, filename):
        self.data = {}
        self.length = 0
        self.info_hash = None
        self.read_torrent(filename)
    
    def read_torrent(self, filename):
        with open(filename, 'rb') as fp:
            data_bencoded = fp.read()

        data_decoded = bencodepy.decode(data_bencoded)
        self.data = self.decode_value(data_decoded)

        #get SHA1 hash of bencoded info dictionary
        info_bencoded = bencodepy.encode(self.data['info'])
        self.info_hash = hashlib.sha1(info_bencoded).digest()

    #recursively decode dictionaries and lists of byte strings to utf-8
    def decode_value(self, value):
            new_value = value

            if isinstance(value, bytes):
                new_value = value.decode()

            if isinstance(value, list):
                new_value = []
                for item in value:
                    new_value.append(self.decode_value(item))

            if isinstance(value, dict):
                new_value = {}
                for key,val in value.items(): 
                    if key == b'pieces': #pieces should stay as bytes
                        new_value[self.decode_value(key)] = val
                    else:
                        new_value[self.decode_value(key)] = self.decode_value(val)

            return new_value




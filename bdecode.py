
import bencodepy

#wraps bencodepy.decode to return dictionary items as utf-8 encoded strings
def decode(data):
     return decode_byte_strings(bencodepy.decode(data))
     
#recursively convert dictionaries and lists of byte strings to utf-8
def decode_byte_strings(value):
        new_value = value

        if isinstance(value, bytes):
            new_value = value.decode('utf-8')

        if isinstance(value, list):
            new_value = []
            for item in value:
                new_value.append(decode_byte_strings(item))

        if isinstance(value, dict):
            new_value = {}
            for key,val in value.items(): 
                if key == b'pieces' or key == b'peers': #these should stay as bytes
                    new_value[decode_byte_strings(key)] = val
                else:
                    new_value[decode_byte_strings(key)] = decode_byte_strings(val)

        return new_value



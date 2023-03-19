import crcmod
import random

crc_16 = crcmod.mkCrcFun(0x18005, initCrc=0, rev=False)


def create_header(flag, seq_num, data):
    new_data = flag.encode('utf-8') + int.to_bytes(seq_num, length=4, byteorder='big')
    if data:
        new_data = new_data + data
    return add_crc(new_data)


def add_crc(data):
    rem = crc_16(data)
    data_s = data[0:5] + int.to_bytes(rem, length=2, byteorder='big') + data[5:]
    return data_s


def check_crc(data):
    if data:
        data_s = data[0:5] + data[7:] + data[5:7]
        if crc_16(data_s) == 0:
            return True
    return False

# Change 3 random bytes in a fragment
def make_mistake(frag):
    frag = bytearray(frag)
    indexes = random.sample(range(0, len(frag)), 3)
    for index in indexes:
        if frag[index] == 0:
            frag[index] = 255
        else:
            frag[index] = 0
    return bytes(frag)




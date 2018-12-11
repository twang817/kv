import struct


def unpack(f, fmt):
    size = struct.calcsize(fmt)
    return struct.unpack(fmt, f.read(size))

def unpack_vls(f):
    data = f.read(4)
    size = struct.unpack('=I', data)
    return f.read(size[0])

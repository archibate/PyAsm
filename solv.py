assert __name__ == '__main__'

from wrinfo import ggldinfo
from wwidr import wwid
import sys
import struct

basadr = 0
bininp = sys.argv[1]
infinp = sys.argv[2]


i = 3
while i < len(sys.argv):
    if sys.argv[i] == '-x':
        i += 1
        basadr = int(sys.argv[i], base=16)
    i += 1


if wwid == 2:
    wordfmt = 'H'
elif wwid == 4:
    wordfmt = 'I'
elif wwid == 8:
    wordfmt = 'L'
else:
    assert 0


adrmap = {}
syms = {}

ggldinfo(infinp, basadr, adrmap, syms)

fbin = open(bininp, 'rb+') if isinstance(bininp, str) else bininp
for sym, pads in syms.items():
    adr = adrmap[sym]
    for pad in pads:
        fbin.seek(pad)
        x = struct.unpack(wordfmt, fbin.read(4))[0]
        x = (x + adr) % (0x100 ** wwid)
        fbin.seek(pad)
        fbin.write(struct.pack(wordfmt, x))

if isinstance(bininp, str): fbin.close()

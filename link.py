assert __name__ == '__main__'

import os, sys
from wrinfo import hexstr2i, ggwrinfo, ggldinfo

ldsinp = None
output = '/dev/null'
infout = sys.stdout

i = 1
while i < len(sys.argv):
    if sys.argv[i] == '-o':
        i += 1
        output = sys.argv[i]
    elif sys.argv[i] == '-u':
        i += 1
        infout = sys.argv[i]
    else:
        ldsinp = sys.argv[i]
    i += 1

basadr = 0
currcmd = None

adrmap = {}
syms = {}

fout = open(output, 'wb') if isinstance(output, str) else output

with open(ldsinp) as flds:
    for line in flds.readlines():
        line = line.split()
        if not len(line):
            continue
        #if line[0][1] == '&':
        #    cmd = line[0][1:]
        #    if cmd == 'setadr':
        #        cmd, basadr = line
        #    continue
        bininp, infinp = line
        ggldinfo(infinp, basadr, adrmap, syms)
        with open(bininp) as fbin:
            bs = fbin.read()
            basadr += len(bs)
            fout.write(bs)

with open(infout, 'wb') as finf:
    ggwrinfo(finf, adrmap, syms)

if isinstance(infout, str): finf.close()
if isinstance(output, str): fout.close()

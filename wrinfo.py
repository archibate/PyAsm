import os, sys


class _clomk_mktmpname:
    def __init__(s):
        s.i = 0
    def __call__(s, ext=''):
        s.i += 1
        bas = '/tmp/tmp' + str(os.getpid())
        return bas + str(s.i) + ext
mktmpname = _clomk_mktmpname()


def print_(*x):
    sys.stdout.write(' '.join(map(str, x)))
    sys.stdout.write('\n')


# tohexstr(0xabc, 4) => '0ABC'
def tohexstr(i, l):
    s = hex(i)[2:].upper()
    return '0' * (l - len(s)) + s


# b'\xfa\xcd\x91' => 'FACD91'
def bstohexstr(bs):
    return ''.join(tohexstr(b, 2) for b in bs)


# 'FACD91' => 0xfacd91
def hexstr2i(x):
    return int('0x'+x,base=16)


def ggwrinfo(finfo, adrmap, syms):
    finfo.write('!!adrm\n')
    for sym, adr in adrmap.items():
        finfo.write(tohexstr(adr, 8))
        finfo.write(' ')
        finfo.write(sym)
        finfo.write('\n')
    finfo.write('!!syms\n')
    for sym, adrs in syms.items():
        finfo.write(sym)
        for adr in adrs:
            finfo.write(' ')
            finfo.write(tohexstr(adr, 8))
        finfo.write('\n')


def ggldinfo(infinp, basadr, adrmap, syms):
    currcmd = None
    with open(infinp) as finf:
        for il in finf.readlines():
            il = il.split()
            if not len(il):
                continue
            if il[0][:2] == '!!':
                currcmd = il[0][2:]
            elif currcmd == 'adrm':
                adr, sym = il
                assert sym not in adrmap
                adrmap[sym] = basadr + hexstr2i(adr)
            elif currcmd == 'syms':
                sym = il[0]
                if sym not in syms:
                    syms[sym] = []
                syms[sym] += [basadr + hexstr2i(adr) for adr in il[1:]]

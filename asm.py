#!/usr/bin/env python

import os
import struct


class _clomk_mktmpname:
    def __init__(s):
        s.i = 0
    def __call__(s, ext=''):
        s.i += 1
        bas = '/tmp/tmp' + str(os.getpid())
        return bas + str(s.i) + ext
mktmpname = _clomk_mktmpname()


# tohex(0xabc, 1) => '0ABC'
def tohexstr(i, l):
    s = hex(i)[2:].upper()
    return '0' * (l - len(s)) + s


# b'\xfa\xcd\x91' => 'FACD91'
def bstohexstr(bs):
    return ''.join(tohexstr(b, 2) for b in bs)


def exeoscmd(*cmds):
    return os.system(' '.join(cmds))


# ehhhhhh....
def donasm(wwid, cmd, *args):
    s = cmd + ' ' + ','.join(args)
    s = 'BITS ' + str(wwid * 8) + '\n' + s
    tmpasm = mktmpname('.asm')
    tmplst = mktmpname('.lst')
    open(tmpasm, 'w+').write(s)
    assert not exeoscmd('nasm', tmpasm, '-l', tmplst, '-o', '/dev/null')
    lst = open(tmplst).read()
    os.unlink(tmpasm)
    os.unlink(tmplst)
    lst = lst.splitlines()[1].split()[2].upper()
    return lst


class UnsvController():
    def __init__(self):
        # our signatures, for accessing the slot offset (embressed nasm)
        ori_ids = [0xface80c9, 0xbeaddeaf, 0xfacbc0de, 0xbacbdea0]
        self.sids = []
        for id in ori_ids:
            sd0 = tohexstr(id, 8)
            sd = ''
            for a, b in zip(sd0[::2], sd0[1::2]):
                sd = a + b + sd
            id, sd = id + id * 0x100000000, sd * 2
            self.sids.append((id, sd))
        self.reset()

    def reset(self):
        self.i = 0
        self.slots = []

    def gen_slot(self, wwid, sym):
        self.i += 1
        self.i %= len(self.sids)
        id, sd = self.sids[self.i]
        id %= 0x100 ** wwid
        sd = sd[:wwid*2]
        self.slots.append((sym, sd))
        return id


class AssemblerError(Exception):
    pass


def efind(m, c):
    r = m.find(c)
    return len(m) if r == -1 else r

def efinds(m, s):
    return min(efind(m, c) for c in '+-')


class Assembler():

    def __init__(self, d, echols=False, addr=0, wwid=4):
        self.d = d
        self.syms = {}
        self.unsv = UnsvController()
        self.usv_sypas = []
        self.wwid = wwid
        self.padr = 0
        self.addr = addr
        self.data = b''
        self.echols = echols


    def lookup_sym(self, m):
        if m == '.': # $. stands for current address in asm
            return self.addr

        sym = m[:efinds(m, '+-')]
        try:
            # if existed, return address
            return self.syms[sym]
        except KeyError:
            # generate an slot in unsv for this symbol (with '+-' info)
            return self.unsv.gen_slot(self.wwid, m)


    @property
    def wordfmt(self): # wwid => struct.fmt
        if self.wwid == 2:
            return 'H'
        elif self.wwid == 4:
            return 'I'
        elif self.wwid == 8:
            return 'L'
        else:
            assert 0


    def define_sym(self, sym, addr=None):
        if addr is None:
            addr = self.addr

        if sym in self.syms:
            raise AssemblerError('symbol already defined: ' + str(sym))

        self.syms[sym] = addr

        # save the oldpos, we will go far
        oldpos = self.d.tell()

        # now slove the unsv symbols!
        i = 0
        while i < len(self.usv_sypas):
            m, padr = self.usv_sypas[i]
            # remove any character in m after one of '+-'
            ei = efinds(m, '+-')
            sym_ = m[:ei]
            if sym_ == sym: # was it refering to me?
                off = int(m[ei:]) if ei != len(m) else 0
                self.d.seek(padr)
                ad = addr + off
                self.d.write(struct.pack(self.wordfmt, ad))
                del self.usv_sypas[i]
                # note: deleted, so now usv_sypas[i] is just the next
                # ****: no need to i++ anymore.
            else:
                i += 1

        # restore the old position
        self.d.seek(oldpos)


    def care_unsolves(self):
        unsolves = {}
        # now left the unsv symbols infos to the linker!
        for m, padr in self.usv_sypas:
            # remove any character in m after one of '+-'
            ei = efinds(m, '+-')
            sym = m[:ei]
            off = int(m[ei:]) if ei != len(m) else 0
            self.d.seek(padr)
            self.d.write(struct.pack(self.wordfmt, off))
            if sym not in unsolves:
                unsolves[sym] = [padr]
            else:
                unsolves[sym].append(padr)
        return unsolves


    def compile(self, cmd, *args):
        lst = donasm(self.wwid, cmd, *args)

        # solve symbol-offset pair into syofs
        idx = 0
        syofs = []
        # get the offset of our signature in the heximal string
        for sym, sd in self.unsv.slots:
            idx = lst.index(sd, idx)
            assert idx % 2 == 0
            off = idx // 2
            syofs.append((sym, off))

        # convert lst into bytes
        hexs = []
        while len(lst):
            h = int(lst[:2], base=16)
            lst = lst[2:]
            hexs.append(h)
        bs = bytes(hexs)

        return bs, syofs


    def parse_arg(self, arg):
        for h in ['$','#','%']:
            # check arg prefix
            if arg[:len(h)] == h:
                m = arg[len(h):]
                if h == '$': # $symbol
                    addr = self.lookup_sym(m)
                    m = hex(addr)
                return m
        raise AssemblerError('cannot parse prefix for: ' + str(arg))


    def on_line(self, line):
        # mov ax, 1 => 'mov ax', '1'
        line = line.strip().split(',')

        # empty line?
        if not len(line):
            return None

        # 'mov ax', '1' => 'mov', 'ax', '1'
        args = line.pop(0).split()
        cmd = args.pop(0).lower()
        ahead = ' '.join(args)
        args = ([ahead] if ahead else []) + line
        args = [a.strip() for a in args]
        # parsing done

        # is special cmd?
        if cmd == '!bits':
            assert len(args) == 1
            bits = int(args[0])
            assert bits % 8 == 0
            self.wwid = bits // 8
            return
        elif cmd == '!orgv':
            assert len(args) == 1
            addr = int(args[0], base=16)
            self.addr = addr
            return
        elif cmd == '!echols':
            assert len(args) == 1
            sett = ['on', 'off'].index(args[0])
            self.echols = True if sett else False
            return
        elif cmd == '!def':
            assert len(args) == 1
            sym = args[0]
            self.define_sym(sym)
            return

        self.unsv.reset() # self.unsv will be used in parse_arg()
        # now check args for symbols
        for i, arg in enumerate(args):
            args[i] = self.parse_arg(arg)

        # will call to nasm to compile it
        bs, syofs = self.compile(cmd, *args)

        # add symbol-phys_addr pairs to usv_sypas
        for sym, off in syofs:
            padr = off + self.padr
            self.usv_sypas.append((sym, padr))
        # this usv_sypas can be dealt in assembler or linker

        if self.echols:
            print(tohexstr(self.addr, 8), bstohexstr(bs), cmd, ', '.join(args))

        self.padr += len(bs)
        self.addr += len(bs)
        self.d.write(bs)


def assem_main(input, output):
    with open(output, 'wb+') as fout:
        asmr = Assembler(fout)
        with open(input) as f:
            for line in f.readlines():
                lst = asmr.on_line(line)
        asmr.care_unsolves() # TODO: output the unsolves info!


output = '/dev/null'
input = '/dev/stdin'

from sys import argv
i = 1
while i < len(argv):
    if argv[i] == '-o':
        i += 1
        output = argv[i]
    else:
        input = argv[i]
    i += 1

assem_main(input, output)
#exeoscmd('hexdump', '-C', output)

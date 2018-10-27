#!/usr/bin/env python

import os, sys
import struct
from wrinfo import ggwrinfo, mktmpname, print_, tohexstr, bstohexstr
from wwidr import wwid


def exeoscmd(*cmds):
    return os.system(' '.join(cmds))


# ehhhhhh....
def donasm(wwid, cmd, *args):
    s = cmd + ' ' + ','.join(map(str, args))
    s = 'BITS ' + str(wwid * 8) + '\n' + s
    tmpasm = mktmpname('.asm')
    tmplst = mktmpname('.lst')
    open(tmpasm, 'w').write(s)
    assert not exeoscmd('nasm', tmpasm, '-l', tmplst, '-o', '/dev/null')
    lst = open(tmplst).read()
    os.unlink(tmpasm)
    os.unlink(tmplst)
    lst = lst.splitlines()[1].split()[2].upper()
    print_(lst, ' ' * (13 - len(lst)), cmd, ','.join(map(str, args)))
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

    def __init__(self, d, wwid=4):
        self.d = d
        self.syms = {}
        self.unsv = UnsvController()
        self.usv_sypas = []
        self.adrmap = {}
        self.wwid = wwid
        self.addr = 0
        self.data = b''


    def lookup_sym(self, m):
        sym = m[:efinds(m, '+-')]
        try:
            # if existed, return address
            return self.syms[sym]
        except KeyError:
            # generate an slot in unsv for this symbol (with '+-' info)
            return self.unsv.gen_slot(self.wwid, m)


    def gen_slot(self, m):
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

        ## save the oldpos, we will go far
        #oldpos = self.d.tell()

        # now slove the unsv symbols!
        #i = 0
        #while i < len(self.usv_sypas):
        #for m, padr in self.usv_sypas:
        #    #m, padr = self.usv_sypas[i]
        #    # remove any character in m after one of '+-'
        #    ei = efinds(m, '+-')
        #    sym_ = m[:ei]
        #    if sym_ == sym: # was it refering to me?
        #        off = int(m[ei:]) if ei != len(m) else 0
        #        self.d.seek(padr)
        #        ad = addr + off
        #        self.d.write(struct.pack(self.wordfmt, ad))
        #        #del self.usv_sypas[i]
        #        ## note: deleted, so now usv_sypas[i] is just the next
        #        ## ****: no need to i++ anymore.
        #    #else:
        #    #    i += 1

        # add addr to solved sym table
        self.adrmap[sym] = addr

        ## restore the old position
        #self.d.seek(oldpos)


    def care_syms(self): # move the fucking slots better
        syms = {}
        # now left the unsv symbols infos to the linker!
        for sypa in self.usv_sypas:
            m, addr = sypa
            # remove any character in m after one of '+-'
            ei = efinds(m, '+-')
            sym, off = m[:ei], m[ei:]
            off = int(off) if ei != len(m) else 0
            self.d.seek(addr)
            if off < 0:
                off = 0x100 ** self.wwid + off
            self.d.write(struct.pack(self.wordfmt, off))
            if sym not in syms:
                syms[sym] = [addr]
            else:
                syms[sym].append(addr)
        return syms


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
        bs = b''
        while len(lst):
            h = int(lst[:2], base=16)
            lst = lst[2:]
            bs += struct.pack('B', h)

        return bs, syofs


    def parse_arg(self, arg):
        # check arg prefix
        h, m = arg[:1], arg[1:]
        if h == '$': # $symbol
            addr = self.gen_slot(m)
            return addr
        elif h == '%': # %reg
            return m
        elif h == '#': # #immediate
            return int(m)
        else:
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
        # now bs is the line compiled result

        # add symbol-phys_addr pairs to usv_sypas
        for sym, off in syofs:
            addr = off + self.addr
            self.usv_sypas.append((sym, addr))
        # this usv_sypas can be dealt in assembler or linker

        self.addr += len(bs)
        self.d.write(bs)


    def write_info(self, finfo):
        syms = self.care_syms()
        ggwrinfo(finfo, self.adrmap, syms)


    def show_unsolves_info(self, unsolves):
        #unsvtab = '\0'.join(sym for sym in unsolves.keys()) + '\0'
        #unsvpds = unsolves.values()

        #unsitp = b''
        print_('\nUNSOLVES:\n')
        for i, (sym, pads) in enumerate(unsolves.items()):
            print_(sym + ':')
            for pad in pads:
                print_('  ' + tohexstr(pad, 8))
                #unsitp += struct.pack(self.wordfmt * 2, i, pad)

        #self.d.seek(0, 2) # SEEK_END
        #self.d.write(unsvtab)


def assem_main(input, output, infout):
    fout = open(output, 'wb') if isinstance(output, str) else output
    fin = open(input) if isinstance(input, str) else input
    asmr = Assembler(fout, wwid)
    for line in fin.readlines():
        lst = asmr.on_line(line)
    if isinstance(input, str): fin.close()
    finfo = open(infout, 'w') if isinstance(infout, str) else infout
    asmr.write_info(finfo)
    if isinstance(output, str): fout.close()
    if isinstance(infout, str): finfo.close()


if __name__ == '__main__':
    output = '/dev/null'
    input = sys.stdin
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
            input = sys.argv[i]
        i += 1

    assem_main(input, output, infout)

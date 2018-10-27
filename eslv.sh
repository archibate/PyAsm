set -e
python solv.py ${1?no out}.bin $1.inf -x ${2-0x0}
rm -f $1.inf

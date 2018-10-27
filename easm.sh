set -e
python asm.py ${1?no asm name}.asm -o $1.bin -u $1.inf

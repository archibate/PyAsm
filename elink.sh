set -e
python link.py ${1?no lds name}.lds -o $1.bin -u $1.inf

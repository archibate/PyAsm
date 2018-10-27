set -e

sh easm.sh test
sh easm.sh team
sh elnk.sh oute test team
hexdump -C oute.bin
sh eslv.sh oute
hexdump -C oute.bin

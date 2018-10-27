set -e
o=${1?no lds name}
shift
echo > $o.lds
for x in $*; do
	echo $x.bin $x.inf >> $o.lds
done

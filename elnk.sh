set -e
sh mklds.sh $*
sh elink.sh ${1?no lds name}

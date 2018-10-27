import sys
from wrinfo import print_

names = sys.argv[1:]

for name in names:
    print_(name + '.bin', name + '.inf')

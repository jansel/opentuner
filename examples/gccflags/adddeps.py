# we would prefer a symbolic link, but it does not work on windows
from past.builtins import execfile
import os
target = os.path.join(os.path.dirname(__file__),
                      '../../opentuner/utils/adddeps.py')
execfile(target, dict(__file__=target))


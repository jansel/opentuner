import os
import sys

proj_root = os.path.normpath(
              os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '../..'))
sys.path.insert(0, proj_root)


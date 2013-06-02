import os
import sys

proj_root = os.path.normpath(
              os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '../..'))
sys.path.insert(0, proj_root)


try:
  from lxml import etree
except ImportError:
  try:
    # Python 2.5
    import xml.etree.cElementTree as etree
  except ImportError:
    import xml.etree.ElementTree as etree




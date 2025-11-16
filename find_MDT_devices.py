import sys, os
root = os.path.dirname(__file__)
src = os.path.join(root, 'src')
if src not in sys.path:
    sys.path.insert(0, src)

from mdt.discovery import *

__all__ = getattr(sys.modules.get('mdt.discovery'), '__all__', [])

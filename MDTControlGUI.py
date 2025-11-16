import sys, os
# Backwards-compatible wrapper for migrated GUI
root = os.path.dirname(__file__)
src = os.path.join(root, 'src')
if src not in sys.path:
    sys.path.insert(0, src)

from mdt.gui import main

if __name__ == '__main__':
    main()

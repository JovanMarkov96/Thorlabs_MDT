import sys
import os

root = os.path.dirname(__file__)
src = os.path.join(root, 'src')
if src not in sys.path:
    sys.path.insert(0, src)

from mdt import discovery


def main():
    """Run the discovery CLI (writes `mdt_devices.json` when --json is used)."""
    discovery.main()


if __name__ == "__main__":
    main()


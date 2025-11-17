#!/usr/bin/env python3
"""Helper to download Thorlabs MDT DLLs into .mdt_dlls/ and verify SHA256.

This script is intentionally conservative: it does not embed or redistribute
DLLs itself. Provide direct download URLs (from Thorlabs or an approved mirror)
and optional SHA256 checksums to verify integrity.

Usage:
  python tools/get_mdt_dlls.py --url <DLL_URL> [--outname MDT_COMMAND_LIB.dll] [--sha256 <hexsum>]

Example:
  python tools/get_mdt_dlls.py --url "https://example.com/MDT_COMMAND_LIB.dll" \
      --outname MDT_COMMAND_LIB.dll --sha256 012345...abcdef

If no URL is provided the script prints instructions and exits.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from urllib.request import urlopen, Request


def download_file(url: str, dest: str) -> None:
    req = Request(url, headers={"User-Agent": "mdt-helper/1.0"})
    with urlopen(req) as r, open(dest, "wb") as fh:
        fh.write(r.read())


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser(description="Download MDT DLLs into .mdt_dlls/")
    p.add_argument("--url", help="Direct URL to a DLL (HTTP/HTTPS)")
    p.add_argument("--outname", help="Output filename (default: same as URL basename)")
    p.add_argument("--sha256", help="Expected SHA256 hex checksum for verification")
    args = p.parse_args(argv)

    if not args.url:
        print("No URL provided. This helper downloads a DLL when you provide a direct URL.")
        print("See docs/obtain_dlls.md for manual instructions to obtain the DLLs from Thorlabs.")
        return 0

    outdir = os.path.join(os.getcwd(), ".mdt_dlls")
    os.makedirs(outdir, exist_ok=True)
    outname = args.outname or os.path.basename(args.url)
    dest = os.path.join(outdir, outname)

    print(f"Downloading {args.url} -> {dest} ...")
    try:
        download_file(args.url, dest)
    except Exception as e:
        print(f"Download failed: {e}")
        return 2

    if args.sha256:
        got = sha256_file(dest)
        if got.lower() != args.sha256.lower():
            print(f"SHA256 mismatch: expected {args.sha256} got {got}")
            return 3
        print("SHA256 verified")
    else:
        print("Downloaded (no SHA256 provided). Consider verifying checksum manually.")

    print("Done. DLL saved to .mdt_dlls/")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

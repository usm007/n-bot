#!/usr/bin/env python3
"""01_download_data.py — Download Kaggle dataset and build index."""
import kagglehub, os, sys

DATA_DIR = '/home/workspace/backtester/data'
os.makedirs(DATA_DIR, exist_ok=True)
DEST = os.path.join(DATA_DIR, 'nifty_options_raw.csv')

print("=" * 60)
print("STEP 1: Downloading Nifty Options Data from Kaggle")
print("=" * 60)
print()
print("Downloading ~6.8 GB — this will take several minutes...")
print()

path = kagglehub.dataset_download('pariminikhil/nifty-option-chain-3-oct-24-to-24-mar-26')
src = os.path.join(path, 'final_merged_output.csv')

print(f"\nCopying to workspace...")
import shutil
shutil.copy2(src, DEST)
size_gb = os.path.getsize(DEST) / (1024**3)
print(f"  ✓ Saved: {DEST}")
print(f"  ✓ Size: {size_gb:.2f} GB")
print()

# Build date index
print("Building date index (one-time)...")
f = open(DEST, 'rb')
f.readline()  # skip header
date_map = {}
pos = f.tell()
total_rows = 0
while True:
    line = f.readline()
    if not line:
        break
    first_comma = line.find(b',')
    d = line[:first_comma].strip()
    if d:
        if d not in date_map:
            date_map[d] = []
        date_map[d].append(pos)
    pos = f.tell()
    total_rows += 1
f.close()

import json
idx_path = os.path.join(DATA_DIR, 'date_index.json')
with open(idx_path, 'w') as jf:
    json.dump({d: date_map[d] for d in sorted(date_map)}, jf)

print(f"  ✓ {total_rows:,} rows indexed across {len(date_map)} dates")
print()
print("=" * 60)
print("STEP 1 COMPLETE — ready to run backtests")
print("=" * 60)
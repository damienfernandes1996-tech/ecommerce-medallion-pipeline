"""Download the Olist CSV files into data/raw (skipped when they are already there)."""
from __future__ import annotations

import urllib.request
from pathlib import Path

from .config import KAGGLE_URL, MIRROR_URL, RAW_FILES, Paths


def download(paths: Paths, force: bool = False) -> list[Path]:
    paths.raw.mkdir(parents=True, exist_ok=True)
    fetched = []
    for filename in RAW_FILES.values():
        target = paths.raw / filename
        if target.exists() and not force:
            print(f"    {filename:<42} already there")
            continue
        url = f"{MIRROR_URL}/{filename}"
        tmp = target.with_suffix(".part")
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as out:
                while chunk := resp.read(1 << 20):
                    out.write(chunk)
        except Exception as exc:  # noqa: BLE001 - give a helpful message, then re-raise
            tmp.unlink(missing_ok=True)
            raise RuntimeError(
                f"Could not download {url}: {exc}\n"
                f"Download the dataset manually from {KAGGLE_URL} and unzip the CSV files "
                f"into {paths.raw}"
            ) from exc
        tmp.replace(target)
        print(f"    {filename:<42} {target.stat().st_size / 1e6:6.1f} MB")
        fetched.append(target)
    return fetched

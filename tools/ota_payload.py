#!/usr/bin/env python3
"""Read partitions from an official A/B full OTA (payload.bin inside the zip).

The OTA may be a local zip or an HTTPS URL; for a URL only the bytes of the
requested partitions are downloaded (HTTP range requests). Integrity is
checked at every level:

* the payload metadata (header, manifest, metadata signature) must have the
  SHA-256 pinned in proprietary/ota-source.json;
* every install operation's data must match its SHA-256 from the manifest;
* the assembled partition must match the manifest's partition hash and the
  pinned partition SHA-256.

Only full-OTA operation types are supported (REPLACE, REPLACE_BZ,
REPLACE_XZ, ZERO and, when the `zstandard` module is available, ZSTD).
"""
from __future__ import annotations

import argparse
import bz2
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
import io
import json
import lzma
import os
from pathlib import Path
import ssl
import struct
import time
import urllib.request
import zipfile

REPLACE, REPLACE_BZ, ZERO, REPLACE_XZ, ZSTD = 0, 1, 6, 8, 14
_CA_BUNDLES = ("/root/.ccr/ca-bundle.crt", "/etc/ssl/certs/ca-certificates.crt")


def _ssl_context() -> ssl.SSLContext:
    for bundle in _CA_BUNDLES:
        if os.path.exists(bundle):
            return ssl.create_default_context(cafile=bundle)
    return ssl.create_default_context()


class OtaError(RuntimeError):
    """The OTA does not match its pinned provenance or cannot be read."""


class _HttpRange(io.RawIOBase):
    """Seekable read-only view of a remote file using HTTP range requests."""

    _BLOCK = 1 << 20

    def __init__(self, url: str):
        super().__init__()
        self.url, self._ctx, self._pos, self._cache = url, _ssl_context(), 0, {}
        head = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(head, context=self._ctx, timeout=60) as resp:
            if resp.headers.get("Accept-Ranges", "").lower() != "bytes":
                raise OtaError(f"{url} does not support byte ranges")
            self.size = int(resp.headers["Content-Length"])

    def fetch(self, start: int, length: int) -> bytes:
        request = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{start + length - 1}"})
        last = None
        for attempt in range(6):
            try:
                with urllib.request.urlopen(request, context=self._ctx, timeout=180) as resp:
                    data = resp.read()
                if len(data) == length:
                    return data
                last = OtaError(f"short read: {len(data)} of {length} bytes")
            # Dropped connections surface as http.client.IncompleteRead, which is not an OSError.
            except (OSError, http.client.HTTPException) as error:
                last = error
            time.sleep(min(2 ** attempt, 30))
        raise OtaError(f"cannot read {length} bytes at {start} from {self.url}: {last}")

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self._pos = {0: offset, 1: self._pos + offset, 2: self.size + offset}[whence]
        return self._pos

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self.size - self._pos
        n = max(0, min(n, self.size - self._pos))
        out = bytearray()
        while n:
            block = self._pos // self._BLOCK
            if block not in self._cache:
                start = block * self._BLOCK
                self._cache[block] = self.fetch(start, min(self._BLOCK, self.size - start))
            data = self._cache[block]
            chunk = data[self._pos - block * self._BLOCK:][:n]
            out += chunk
            self._pos += len(chunk)
            n -= len(chunk)
        return bytes(out)


class _LocalFile:
    def __init__(self, path: Path):
        self.path, self.size = path, path.stat().st_size

    def fetch(self, start: int, length: int) -> bytes:
        with self.path.open("rb") as f:
            f.seek(start)
            data = f.read(length)
        if len(data) != length:
            raise OtaError(f"{self.path}: short read at {start}")
        return data


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = value = 0
    while True:
        byte = buf[i]
        i += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, i
        shift += 7


def _fields(buf: bytes):
    """Yield (field number, value) of a protobuf message (wire types 0, 1, 2, 5)."""
    i = 0
    while i < len(buf):
        key, i = _varint(buf, i)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, i = _varint(buf, i)
        elif wire == 2:
            length, i = _varint(buf, i)
            value, i = buf[i:i + length], i + length
        elif wire == 1:
            value, i = buf[i:i + 8], i + 8
        elif wire == 5:
            value, i = buf[i:i + 4], i + 4
        else:
            raise OtaError(f"unsupported protobuf wire type {wire}")
        yield number, value


def parse_manifest(manifest: bytes) -> tuple[int, dict]:
    """Return (block size, {partition name: {size, hash, ops}}) of a DeltaArchiveManifest."""
    block_size, partitions = 4096, {}
    for number, value in _fields(manifest):
        if number == 3:
            block_size = value
        elif number == 13:
            part = {"name": None, "size": None, "hash": None, "ops": []}
            for field, item in _fields(value):
                if field == 1:
                    part["name"] = item.decode()
                elif field == 7:
                    for key, info in _fields(item):
                        if key == 1:
                            part["size"] = info
                        elif key == 2:
                            part["hash"] = info.hex()
                elif field == 8:
                    op = {"type": REPLACE, "offset": 0, "length": 0, "dst": [], "sha256": None}
                    for key, info in _fields(item):
                        if key == 1:
                            op["type"] = info
                        elif key == 2:
                            op["offset"] = info
                        elif key == 3:
                            op["length"] = info
                        elif key == 6:
                            extent = dict(_fields(info))
                            op["dst"].append((extent.get(1, 0), extent.get(2, 0)))
                        elif key == 8:
                            op["sha256"] = info.hex()
                    part["ops"].append(op)
            partitions[part["name"]] = part
    return block_size, partitions


class Ota:
    """An official full OTA zip, local or remote, checked against ota-source.json."""

    def __init__(self, location: str, source: dict):
        self.source = source
        remote = location.startswith("https://")
        self._reader = _HttpRange(location) if remote else _LocalFile(Path(location))
        if self._reader.size != source["ota"]["size"]:
            raise OtaError(f"OTA size {self._reader.size} != pinned {source['ota']['size']}")
        if remote:
            info = zipfile.ZipFile(self._reader).getinfo("payload.bin")
        else:
            with Path(location).open("rb") as handle:
                info = zipfile.ZipFile(handle).getinfo("payload.bin")
        if info.compress_type != zipfile.ZIP_STORED:
            raise OtaError("payload.bin is compressed inside the zip")
        local = self._reader.fetch(info.header_offset, 30)
        name_len, extra_len = struct.unpack("<HH", local[26:30])
        payload = info.header_offset + 30 + name_len + extra_len
        header = self._reader.fetch(payload, 24)
        if header[:4] != b"CrAU":
            raise OtaError("payload.bin is not an A/B update payload")
        version, manifest_size = struct.unpack(">QQ", header[4:20])
        signature_size = struct.unpack(">I", header[20:24])[0] if version >= 2 else 0
        meta_size = 24 + manifest_size + signature_size
        pinned = source["ota"]["payload_metadata"]
        if (payload, meta_size) != (pinned["offset"], pinned["size"]):
            raise OtaError("payload metadata location differs from the pinned OTA")
        metadata = self._reader.fetch(payload, meta_size)
        if hashlib.sha256(metadata).hexdigest() != pinned["sha256"]:
            raise OtaError("payload metadata SHA-256 differs from the pinned official OTA")
        self.block_size, self.partitions = parse_manifest(metadata[24:24 + manifest_size])
        self._data_start = payload + meta_size

    def extract(self, name: str, out: Path, jobs: int = 6, progress=None) -> str:
        """Write partition `name` to `out`; return its verified SHA-256."""
        part = self.partitions.get(name)
        pinned = self.source["partitions"].get(name)
        if part is None or pinned is None:
            raise OtaError(f"partition {name} is not in the OTA or not pinned")
        if part["size"] != pinned["size"]:
            raise OtaError(f"{name}: size {part['size']} != pinned {pinned['size']}")
        try:
            import zstandard  # optional: only ZSTD operations need it
        except ImportError:
            zstandard = None

        def materialize(op):
            data = self._reader.fetch(self._data_start + op["offset"], op["length"]) if op["length"] else b""
            if op["sha256"] and hashlib.sha256(data).hexdigest() != op["sha256"]:
                raise OtaError(f"{name}: operation data hash mismatch")
            if op["type"] == REPLACE:
                return data
            if op["type"] == REPLACE_BZ:
                return bz2.decompress(data)
            if op["type"] == REPLACE_XZ:
                return lzma.decompress(data)
            if op["type"] == ZSTD and zstandard is not None:
                return zstandard.ZstdDecompressor().decompress(data, max_output_size=1 << 31)
            raise OtaError(f"{name}: unsupported operation type {op['type']}")

        ops = [op for op in part["ops"] if op["type"] != ZERO]
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("wb") as f, ThreadPoolExecutor(max_workers=jobs) as pool:
            f.truncate(part["size"])
            for done, (op, raw) in enumerate(zip(ops, pool.map(materialize, ops)), 1):
                pos = 0
                for start, count in op["dst"]:
                    f.seek(start * self.block_size)
                    f.write(raw[pos:pos + count * self.block_size])
                    pos += count * self.block_size
                if progress:
                    progress(done, len(ops))
        digest = hashlib.sha256()
        with out.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        sha = digest.hexdigest()
        if sha != part["hash"] or sha != pinned["sha256"]:
            raise OtaError(f"{name}: assembled partition SHA-256 {sha} is not the pinned one")
        return sha


def rank_urls(urls: list[str], probe: int = 4 << 20) -> list[str]:
    """Order equivalent mirrors by measured throughput; unreachable ones go last.

    Every byte is verified against the pinned hashes, so the choice of mirror
    never affects integrity, only speed.
    """
    speeds = {}
    for url in urls:
        try:
            reader = _HttpRange(url)
            begin = time.monotonic()
            reader.fetch(reader.size // 2, probe)
            speeds[url] = probe / max(time.monotonic() - begin, 1e-3)
        except (OtaError, OSError, http.client.HTTPException):
            speeds[url] = 0.0
    return sorted(urls, key=lambda u: -speeds[u])


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ota", help="local zip or https URL (default: first pinned URL)")
    p.add_argument("--partition", default="vendor")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--jobs", type=int, default=6)
    args = p.parse_args()
    source = json.loads((root / "proprietary/ota-source.json").read_text())
    ota = Ota(args.ota or rank_urls(source["ota"]["urls"])[0], source)
    sha = ota.extract(args.partition, args.out, args.jobs,
                      lambda done, total: print(f"\r{args.partition}: {done}/{total}", end="", flush=True))
    print(f"\n[PASS] {args.partition}: {args.out} sha256 {sha}")


if __name__ == "__main__":
    main()

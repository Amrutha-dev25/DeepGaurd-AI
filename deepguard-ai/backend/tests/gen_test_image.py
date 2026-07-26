"""Generate a small test PNG for the NIM diagnostic call."""
import struct, zlib, os

def make_png(w, h, r, g, b):
    """Create a minimal solid-color PNG."""
    raw = b""
    for y in range(h):
        raw += b"\x00" + bytes([r, g, b] * w)
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )

path = "D:/adk-workspace/deepguard-ai/backend\tests\test_diag.png"
with open(path, "wb") as f:
    f.write(make_png(64, 64, 200, 100, 50))
print(f"Wrote {path} ({os.path.getsize(path)} bytes)")

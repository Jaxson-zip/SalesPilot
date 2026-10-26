"""演示票据文件：不依赖第三方库，生成一张合法的 PDF 发票和一张 PNG 小票。"""

import struct
import zlib


def invoice_pdf(title: str, amount_yuan: str) -> bytes:
    """单页 PDF（Helvetica，ASCII 文本），带正确的 xref，可被浏览器直接预览。"""
    text = f"BT /F1 20 Tf 60 760 Td ({title}) Tj 0 -36 Td (Amount: CNY {amount_yuan}) Tj ET"
    stream = text.encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def _chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def receipt_png(width: int = 240, height: int = 360) -> bytes:
    """浅灰底 + 横线的「小票」图片（RGB，8 bit）。"""
    rows = bytearray()
    for y in range(height):
        line = y % 24 == 12 and 20 < y < height - 20
        shade = 150 if line else 246
        rows += b"\x00" + bytes([shade, shade, shade]) * width
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )

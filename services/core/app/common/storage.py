"""本地文件存储（UPLOAD_DIR）：票据等附件。

storage_key 由服务端生成（<owner_type>/<owner_id>/<attachment_id><ext>），不使用用户提供的文件名，
防止路径穿越；文件类型按文件头识别，不信任客户端声明的 Content-Type。
"""

from pathlib import Path

from app.common.config import get_settings

# 文件头 → (mime, 扩展名)
_SIGNATURES: list[tuple[bytes, str, str]] = [
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
]
EXTENSIONS: dict[str, tuple[str, ...]] = {
    "application/pdf": (".pdf",),
    "image/png": (".png",),
    "image/jpeg": (".jpg", ".jpeg"),
}


def detect_mime(head: bytes) -> str | None:
    for magic, mime, _ in _SIGNATURES:
        if head.startswith(magic):
            return mime
    return None


def extension_of(mime: str) -> str:
    return EXTENSIONS.get(mime, ("",))[0]


def name_matches(file_name: str, mime: str) -> bool:
    """文件扩展名必须与识别出的类型一致（a.exe 改名成 a.pdf 但内容不是 PDF 的会被文件头拦下）。"""
    return Path(file_name).suffix.lower() in EXTENSIONS.get(mime, ())


def root() -> Path:
    return Path(get_settings().upload_dir).resolve()


def path_of(storage_key: str) -> Path:
    base = root()
    path = (base / storage_key).resolve()
    if base not in path.parents:
        raise ValueError("非法的 storage_key")
    return path


def save(storage_key: str, content: bytes) -> None:
    path = path_of(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def remove(storage_key: str) -> None:
    """删除文件；所在目录空了就一并删除。"""
    path = path_of(storage_key)
    path.unlink(missing_ok=True)
    if path.parent != root() and path.parent.is_dir() and not any(path.parent.iterdir()):
        path.parent.rmdir()

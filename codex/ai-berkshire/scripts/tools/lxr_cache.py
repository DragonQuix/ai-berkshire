"""理杏仁本地磁盘缓存层 — 降低 API 调用频率，零外部依赖（仅 stdlib）。

设计要点：
- 缓存目录：``tempfile.gettempdir() / "lxr_cache"``（跨平台，Windows 兼容；不硬编码 POSIX 临时目录）。
- 存储格式：JSON 文件，文件名 = 请求指纹的 SHA1（endpoint + payload，**去除 token** 后排序）。
- TTL 过期视为 miss；TTL 为 None 或 <=0 表示不缓存。
- 缓存值原样为已解析的 Python 对象（dict/list），序列化为 JSON 存储。
- 命中时直接返回内存对象，避免网络与解压开销，目标 < 10ms。

供 lxr_client 透明使用；上层 lxr_data 按数据类型选择 TTL。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from typing import Any, Optional, Tuple

_DEFAULT_DIR_NAME = "lxr_cache"


class DiskCache:
    """简单的 TTL 磁盘缓存。线程安全（单进程内），跨进程共享同一目录。"""

    def __init__(self, dir_path: Optional[str] = None, enabled: bool = True):
        if dir_path:
            self.dir = os.path.join(dir_path, _DEFAULT_DIR_NAME)
            os.makedirs(self.dir, exist_ok=True)
        else:
            self.dir = os.path.join(tempfile.gettempdir(), _DEFAULT_DIR_NAME)
            os.makedirs(self.dir, exist_ok=True)
        self.enabled = enabled
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(endpoint: str, payload: dict) -> str:
        """生成请求指纹：剔除 token 等敏感字段后排序序列化并 SHA1。"""
        safe = {k: v for k, v in payload.items() if k not in ("token",)}
        fingerprint = json.dumps(
            {"endpoint": endpoint, "payload": safe},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> str:
        return os.path.join(self.dir, f"{key}.json")

    def get(self, endpoint: str, payload: dict, ttl_seconds: Optional[float]) -> Tuple[bool, Any]:
        """返回 (hit, value)。hit=False 时 value 为 None。"""
        if not self.enabled or ttl_seconds is None or ttl_seconds <= 0:
            with self._lock:
                self._misses += 1
            return False, None
        key = self._make_key(endpoint, payload)
        path = self._path(key)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            with self._lock:
                self._misses += 1
            return False, None
        if (time.time() - mtime) > ttl_seconds:
            with self._lock:
                self._misses += 1
            return False, None
        try:
            with open(path, "r", encoding="utf-8") as f:
                value = json.load(f)
        except (OSError, ValueError):
            with self._lock:
                self._misses += 1
            return False, None
        with self._lock:
            self._hits += 1
        return True, value

    def set(self, endpoint: str, payload: dict, value: Any) -> None:
        if not self.enabled or value is None:
            return
        key = self._make_key(endpoint, payload)
        path = self._path(key)
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError:
            pass

    def clear(self) -> int:
        removed = 0
        with self._lock:
            for name in os.listdir(self.dir):
                if name.endswith(".json"):
                    try:
                        os.remove(os.path.join(self.dir, name))
                        removed += 1
                    except OSError:
                        pass
            self._hits = 0
            self._misses = 0
        return removed

    def stats(self) -> dict:
        with self._lock:
            return {"hits": self._hits, "misses": self._misses, "dir": self.dir}

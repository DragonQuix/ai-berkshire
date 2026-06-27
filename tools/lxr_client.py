"""理杏仁 Open API 客户端 — 纯 stdlib（urllib），处理 token/限流/重试/错误/gzip。

技术约束（来自理杏仁 API 注意事项）：
- 全部 POST，Content-Type: application/json。
- Accept-Encoding 必须包含 gzip（本客户端手动解压）。
- 每请求必带 token 参数。
- 速率：1000 次/分钟，36 次/秒；超限返回 429。
- 单次最多 10 年数据；多股票 ≤48 指标/股，单股票 ≤128 指标。

错误处理：
- 429：指数退避重试（1s→2s→4s→8s…，上限 backoff_max）。
- 5xx / 连接错误 / 超时：同样重试。
- 400 校验错误：抛 LixingerValidationError（不重试，附字段级消息）。
- 401/403 鉴权错误：抛 LixingerAuthError（不重试，提示更新 token）。
- 业务层 code != 1：抛 LixingerError（携带 message）。

token 解析优先级：环境变量 token_env（默认 LIXINGER_TOKEN）→ 配置文件 token 字段 → 抛错。
"""

from __future__ import annotations

import gzip
import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from lxr_cache import DiskCache

_CONFIG_FILENAME = "lxr_config.json"
_EXAMPLE_FILENAME = "lxr_config.example.json"


class LixingerError(Exception):
    """理杏仁调用基类异常。"""


class LixingerAuthError(LixingerError):
    """token 缺失或无效。"""


class LixingerRateLimitError(LixingerError):
    """429 限流且重试已耗尽。"""


class LixingerValidationError(LixingerError):
    """请求参数校验失败（400），携带字段级错误消息。"""

    def __init__(self, message: str, details: Optional[list] = None):
        super().__init__(message)
        self.details = details or []


class LixingerServerError(LixingerError):
    """5xx 服务端错误且重试已耗尽。"""


class LixingerTimeout(LixingerError):
    """请求超时且重试已耗尽。"""


def _load_config(config_path: Optional[str]) -> dict:
    """加载配置文件。优先显式路径，其次本文件同目录 lxr_config.json，再退到 example。"""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if config_path:
        candidates.append(config_path)
    candidates.append(os.path.join(here, _CONFIG_FILENAME))
    candidates.append(os.path.join(here, _EXAMPLE_FILENAME))
    for path in candidates:
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}


class LixingerClient:
    """理杏仁 API 同步客户端。线程安全（节流与缓存均加锁）。"""

    def __init__(
        self,
        config_path: Optional[str] = None,
        token: Optional[str] = None,
        config: Optional[dict] = None,
        enable_throttle: bool = True,
    ):
        self.config = config if config is not None else _load_config(config_path)
        req_cfg = self.config.get("request", {})
        self.timeout = float(req_cfg.get("timeout_seconds", 30))
        self.max_retries = int(req_cfg.get("max_retries", 4))
        self.backoff_base = float(req_cfg.get("backoff_base_seconds", 1.0))
        self.backoff_max = float(req_cfg.get("backoff_max_seconds", 16.0))
        self.min_interval = float(req_cfg.get("min_interval_seconds", 0.03)) if enable_throttle else 0.0
        self.base_url = self.config.get("base_url", "https://open.lixinger.com/api/")

        self._token = self._resolve_token(token)
        cache_cfg = self.config.get("cache", {})
        self.cache = DiskCache(
            dir_path=cache_cfg.get("dir"),
            enabled=bool(cache_cfg.get("enabled", True)),
        )
        self._last_call_ts = 0.0
        self._throttle_lock = threading.Lock()

    def _resolve_token(self, explicit: Optional[str]) -> str:
        if explicit:
            return explicit
        env_name = self.config.get("token_env", "LIXINGER_TOKEN")
        tok = os.environ.get(env_name, "").strip()
        if tok:
            return tok
        tok = str(self.config.get("token", "") or "").strip()
        if tok:
            return tok
        raise LixingerAuthError(
            f"未找到理杏仁 token：环境变量 {env_name} 未设置，且配置文件 token 字段为空。"
            "请在环境变量中设置 token 或填写 tools/lxr_config.json。"
        )

    @property
    def token(self) -> str:
        return self._token

    def _throttle(self) -> None:
        if self.min_interval <= 0:
            return
        with self._throttle_lock:
            now = time.monotonic()
            wait = self.min_interval - (now - self._last_call_ts)
            if wait > 0:
                time.sleep(wait)
            self._last_call_ts = time.monotonic()

    def _build_request(self, endpoint: str, payload: dict) -> urllib.request.Request:
        url = self.base_url + endpoint
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept-Encoding": "gzip, deflate",
            },
        )

    def _read_response(self, resp) -> bytes:
        raw = resp.read()
        hdrs = getattr(resp, "headers", None)
        enc = None
        if hdrs is not None:
            try:
                enc = hdrs.get("Content-Encoding")
            except Exception:
                enc = None
        if enc == "gzip" and raw:
            try:
                raw = gzip.decompress(raw)
            except OSError:
                pass
        return raw

    def _parse_payload(self, endpoint: str, payload: dict) -> dict:
        """注入 token 并返回可发送的 payload（不修改调用方字典，且 token 不进入缓存键）。"""
        out = dict(payload)
        out["token"] = self._token
        return out

    def post(self, endpoint: str, payload: dict, ttl_seconds: Optional[float] = None) -> dict:
        """调用一个理杏仁端点并返回 ``data`` 字段（业务数据）。

        - ``ttl_seconds`` 非 None 时先查本地缓存；命中则直接返回缓存值。
        - 返回的是响应中 ``data`` 的内容（list 或 dict）；外层 code/message 不返回。
        - 失败抛出对应的 LixingerError 子类。
        """
        full_payload = self._parse_payload(endpoint, payload)
        hit, cached = self.cache.get(endpoint, full_payload, ttl_seconds)
        if hit:
            return cached

        data = self._post_with_retry(endpoint, full_payload)
        self.cache.set(endpoint, full_payload, data)
        return data

    def post_raw(self, endpoint: str, payload: dict) -> dict:
        """调用端点并返回完整响应 dict（含 code/message/data），不缓存。用于调试。"""
        full_payload = self._parse_payload(endpoint, payload)
        return self._post_with_retry(endpoint, full_payload, return_full=True)

    def _post_with_retry(self, endpoint: str, full_payload: dict, return_full: bool = False) -> dict:
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                req = self._build_request(endpoint, full_payload)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = self._read_response(resp)
            except urllib.error.HTTPError as e:
                last_exc = e
                body = b""
                try:
                    body = self._read_response(e)
                except Exception:
                    pass
                text = body.decode("utf-8", errors="replace") if body else ""
                parsed = self._safe_json(text)
                if e.code == 429:
                    if attempt < self.max_retries:
                        self._sleep_backoff(attempt)
                        continue
                    raise LixingerRateLimitError(f"429 限流，重试 {self.max_retries} 次仍失败: {text[:200]}")
                if e.code in (400,):
                    raise self._build_validation_error(text, parsed)
                if e.code in (401, 403):
                    msg = parsed.get("message") if parsed else None
                    raise LixingerAuthError(f"{e.code} 鉴权失败：{msg or text[:200]}（请更新 token）")
                if 500 <= e.code < 600:
                    if attempt < self.max_retries:
                        self._sleep_backoff(attempt)
                        continue
                    raise LixingerServerError(f"{e.code} 服务端错误: {text[:200]}")
                raise LixingerError(f"HTTP {e.code}: {text[:200]}")
            except urllib.error.URLError as e:
                last_exc = e
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise LixingerError(f"网络错误: {e}") from e
            except TimeoutError as e:
                last_exc = e
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise LixingerTimeout(f"请求超时: {e}") from e

            parsed = self._safe_json(raw.decode("utf-8", errors="replace"))
            if not isinstance(parsed, dict):
                raise LixingerError(f"响应非 JSON 对象: {raw[:200]!r}")
            code = parsed.get("code")
            if code != 1:
                msg = parsed.get("message") or parsed.get("msg") or ""
                err = parsed.get("error")
                if err and isinstance(err, dict) and err.get("messages"):
                    raise self._build_validation_error("", parsed)
                raise LixingerError(f"业务错误 code={code}: {msg}")
            if return_full:
                return parsed
            return parsed.get("data")
        # 理论上不会到达
        raise LixingerError(f"请求失败，已耗尽重试: {last_exc}")

    def _sleep_backoff(self, attempt: int) -> None:
        delay = min(self.backoff_max, self.backoff_base * (2 ** attempt))
        time.sleep(delay)

    @staticmethod
    def _safe_json(text: str) -> dict:
        if not text:
            return {}
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {}
        except ValueError:
            return {}

    @staticmethod
    def _build_validation_error(text: str, parsed: dict) -> LixingerValidationError:
        messages: list = []
        name = ""
        if parsed:
            err = parsed.get("error") or {}
            name = err.get("name", "") if isinstance(err, dict) else ""
            msgs = err.get("messages") if isinstance(err, dict) else None
            if isinstance(msgs, list):
                messages = msgs
        summary = name or "ValidationError"
        if messages:
            summary += ": " + "; ".join(
                str(m.get("message", m)) if isinstance(m, dict) else str(m) for m in messages
            )
        elif text:
            summary += ": " + text[:200]
        return LixingerValidationError(summary, details=messages)

    def check_token(self) -> bool:
        """轻量校验 token 是否可用。返回 True/False，不抛异常。"""
        try:
            self.post(
                "cn/company/fs/non_financial",
                {"stockCodes": ["600519"], "date": "latest", "metricsList": ["q.ps.toi.t"]},
                ttl_seconds=None,
            )
            return True
        except LixingerAuthError:
            return False
        except LixingerError:
            return True

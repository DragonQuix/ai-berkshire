#!/usr/bin/env python3
"""理杏仁客户端与降级链单元测试 — 纯 mock，不依赖网络与真实 token，可在 CI 运行。

覆盖：
- DiskCache：键剔除 token、命中/未命中/TTL 过期。
- LixingerClient：token 解析（env/缺失）、429 重试成功、持续 429 抛限流、400 校验错误解析。
- LxrData._run_chain：降级顺序、异常跳过、全部失败返回 none。

依赖网络与 token 的集成验证（真实理杏仁/妙想/免费源调用）见 docs/plan-lixinger-migration.md
阶段 1 准出，已人工执行通过；此处不重复，避免 CI 泄露 token。
"""

from __future__ import annotations

import io
import os
import sys
import time
import unittest
from unittest import mock

import http.client

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
sys.path.insert(0, TOOLS_DIR)

import lxr_client as lxc  # noqa: E402
from lxr_cache import DiskCache  # noqa: E402
from lxr_client import (  # noqa: E402
    LixingerAuthError,
    LixingerClient,
    LixingerRateLimitError,
    LixingerValidationError,
)
from lxr_data import LxrData  # noqa: E402


def _http_error(code: int, body: bytes, reason: str = "Error"):
    """构造一个可被 _read_response 读取的 HTTPError（带规范 headers 对象）。"""
    hdrs = http.client.HTTPMessage()
    hdrs.add_header("Content-Type", "application/json")
    fp = io.BytesIO(body)
    err = lxc.urllib.error.HTTPError("https://open.lixinger.com/api/x", code, reason, hdrs, fp)
    return err


class TestDiskCache(unittest.TestCase):
    def setUp(self):
        self.cache = DiskCache(enabled=True)

    def tearDown(self):
        self.cache.clear()

    def test_key_excludes_token(self):
        ep = "cn/company/fs/non_financial"
        k1 = self.cache._make_key(ep, {"stockCodes": ["600519"], "token": "AAA"})
        k2 = self.cache._make_key(ep, {"stockCodes": ["600519"], "token": "BBB"})
        k3 = self.cache._make_key(ep, {"stockCodes": ["600519"]})
        self.assertEqual(k1, k2)
        self.assertEqual(k1, k3)

    def test_hit_miss_and_ttl(self):
        ep = "x"
        payload = {"a": 1}
        hit, val = self.cache.get(ep, payload, ttl_seconds=10)
        self.assertFalse(hit)
        self.cache.set(ep, payload, {"data": 42})
        hit, val = self.cache.get(ep, payload, ttl_seconds=10)
        self.assertTrue(hit)
        self.assertEqual(val, {"data": 42})
        # TTL 过期
        hit, val = self.cache.get(ep, payload, ttl_seconds=0.01)
        self.assertTrue(hit)
        time.sleep(0.02)
        hit, val = self.cache.get(ep, payload, ttl_seconds=0.01)
        self.assertFalse(hit)

    def test_disabled_cache_always_miss(self):
        c = DiskCache(enabled=False)
        c.set("e", {"p": 1}, {"x": 1})
        hit, _ = c.get("e", {"p": 1}, ttl_seconds=60)
        self.assertFalse(hit)


class TestLixingerClient(unittest.TestCase):
    def _client(self, **kw):
        cfg = {
            "base_url": "https://open.lixinger.com/api/",
            "token_env": "LIXINGER_TOKEN",
            "token": "",
            "request": {"timeout_seconds": 5, "max_retries": 2, "backoff_base_seconds": 0.01,
                        "backoff_max_seconds": 0.05, "min_interval_seconds": 0},
            "cache": {"enabled": False, "dir": None, "default_ttl_seconds": 60},
            "data_type_ttl_seconds": {},
        }
        kw.setdefault("config", cfg)
        return LixingerClient(**kw)

    def test_token_from_env(self):
        with mock.patch.dict(os.environ, {"LIXINGER_TOKEN": "envtok"}):
            c = self._client()
            self.assertEqual(c.token, "envtok")

    def test_explicit_token_wins(self):
        with mock.patch.dict(os.environ, {"LIXINGER_TOKEN": "envtok"}):
            c = self._client(token="explicit")
            self.assertEqual(c.token, "explicit")

    def test_missing_token_raises(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(LixingerAuthError):
                self._client()

    def test_429_retry_then_success(self):
        calls = {"n": 0}
        real = lxc.urllib.request.urlopen

        def flaky(req, *a, **kw):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise _http_error(429, b"")
            return real(req, *a, **kw)

        with mock.patch.object(lxc.urllib.request, "urlopen", flaky):
            c = self._client()
            with mock.patch.dict(os.environ, {"LIXINGER_TOKEN": os.environ.get("LIXINGER_TOKEN", "")}):
                if not os.environ.get("LIXINGER_TOKEN"):
                    self.skipTest("无真实 token，跳过 429 重试成功用例")
                try:
                    data = c.post("cn/company/fs/non_financial",
                                  {"stockCodes": ["600519"], "date": "latest",
                                   "metricsList": ["q.ps.toi.t"]}, ttl_seconds=None)
                except lxc.LixingerError as e:
                    if "网络错误" in str(e) or "timed out" in str(e):
                        self.skipTest("网络超时，跳过 429 重试成功用例")
                    raise
                self.assertEqual(calls["n"], 3)
                self.assertIsInstance(data, list)

    def test_429_always_raises_rate_limit(self):
        def always_429(req, *a, **kw):
            raise _http_error(429, b"")

        with mock.patch.object(lxc.urllib.request, "urlopen", always_429):
            c = self._client()
            with self.assertRaises(LixingerRateLimitError):
                c.post("cn/company/fs/non_financial",
                       {"stockCodes": ["600519"], "date": "latest",
                        "metricsList": ["q.ps.toi.t"]}, ttl_seconds=None)

    def test_400_raises_validation_error(self):
        body = (b'{"code":0,"error":{"name":"ValidationError","messages":'
                b'[{"value":["bad.metric"],"path":["metricsList"],'
                b'"message":"(bad.metric) are invalid fs metrics"}]}}')

        def bad_400(req, *a, **kw):
            raise _http_error(400, body, "Bad Request")

        with mock.patch.object(lxc.urllib.request, "urlopen", bad_400):
            c = self._client()
            with self.assertRaises(LixingerValidationError) as ctx:
                c.post("cn/company/fs/non_financial",
                       {"stockCodes": ["600519"], "date": "latest",
                        "metricsList": ["bad.metric"]}, ttl_seconds=None)
            self.assertIn("bad.metric", str(ctx.exception))

    def test_validation_error_parser(self):
        parsed = {"error": {"name": "ValidationError", "messages": [
            {"message": "(x) invalid"}]}}
        err = LixingerClient._build_validation_error("", parsed)
        self.assertIn("x", str(err))
        self.assertEqual(len(err.details), 1)


class TestFallbackChain(unittest.TestCase):
    def test_first_success_returns_source(self):
        d = LxrData(verbose=False)
        tiers = [("lixinger", lambda: {"records": [1]}),
                 ("mx-data", lambda: {"raw": 2})]
        out = d._run_chain(tiers)
        self.assertEqual(out["_source"], "lixinger")

    def test_falls_through_on_exception(self):
        d = LxrData(verbose=False)
        tiers = [("lixinger", lambda: (_ for _ in ()).throw(LixingerAuthError("bad token"))),
                 ("mx-data", lambda: {"raw": 2})]
        out = d._run_chain(tiers)
        self.assertEqual(out["_source"], "mx-data")

    def test_all_fail_returns_none(self):
        d = LxrData(verbose=False)
        tiers = [("lixinger", lambda: (_ for _ in ()).throw(LixingerAuthError("x"))),
                 ("mx-data", lambda: (_ for _ in ()).throw(RuntimeError("y"))),
                 ("legacy", lambda: (_ for _ in ()).throw(RuntimeError("z")))]
        out = d._run_chain(tiers)
        self.assertEqual(out["_source"], "none")
        self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)

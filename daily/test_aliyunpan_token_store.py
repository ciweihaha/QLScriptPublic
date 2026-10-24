#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aliyunpan.py 刷新令牌 sidecar 持久化回归测试（全程 mock，不调用真实网络）。

覆盖场景：
1. 刷新成功且服务端轮换令牌 → 写回 sidecar（权限 0600），且“新进程视角”
   （重新加载模块 + 重新走 main() 的账号构建）读到的是新令牌而非环境变量旧值；
2. 刷新响应缺 refresh_token → 不写回、旧令牌保留、刷新仍成功并有 warning；
3. 写回失败（目标路径不可写）→ 签到主流程不崩、有 error 日志，且日志不含令牌原文；
4. 双账号：只更新目标账号条目，另一账号条目原样保留；
5. sidecar 不存在 → 纯环境变量行为与改造前一致（令牌原样传入、不生成 sidecar）。

运行：python3 -m unittest test_aliyunpan_token_store -v（在本目录下）
"""

import importlib.util
import json
import os
import stat
import tempfile
import unittest
from unittest import mock

SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aliyunpan.py")


def load_aliyunpan(module_name):
    """以独立模块名加载 aliyunpan.py，模拟新进程重新导入。"""
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeSession:
    """假 Session：post() 直接返回预设 JSON 响应，绝不发网络请求。"""

    def __init__(self, payload):
        self._payload = payload

    def post(self, url, json=None, timeout=None, **_kwargs):
        return _FakeResponse(self._payload)


class _RecordingAliYun:
    """记录 main() 构建账号时传入的 refresh_token，用于验证令牌来源优先级。"""

    instances = []

    def __init__(self, name, refresh_token):
        self.name = name
        self.refresh_token = refresh_token
        _RecordingAliYun.instances.append(self)

    def run(self):
        return "【%s】签到成功（mock）" % self.name


class TestTokenStore(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store_path = os.path.join(self._tmpdir.name, ".aliyunpan_tokens.json")
        _RecordingAliYun.instances = []

    def tearDown(self):
        self._tmpdir.cleanup()

    def _env(self, accounts=None):
        env = {"ALIYUNPAN_TOKEN_STORE": self.store_path}
        if accounts is not None:
            env["ALIYUN_ACCOUNTS"] = accounts
        return mock.patch.dict(os.environ, env)

    def _read_store(self):
        with open(self.store_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _run_main(self, mod):
        with mock.patch.object(mod, "ALiYun", _RecordingAliYun), \
             mock.patch.object(mod, "send_notify", lambda *a, **k: True), \
             mock.patch("time.sleep", lambda *_a, **_k: None), \
             mock.patch("random.randint", lambda a, b: 0):
            mod.main()

    def test_refresh_rotates_persists_and_new_process_reads_new_token(self):
        with self._env("old_tok#账号甲"):
            mod = load_aliyunpan("aliyunpan_store_rotate")
            client = mod.ALiYun("账号甲", "old_tok")
            client.session = _FakeSession({"access_token": "acc", "refresh_token": "new_tok"})
            self.assertTrue(client._refresh_access_token())
            self.assertEqual(client.refresh_token, "new_tok")
            self.assertEqual(self._read_store(), {"账号甲": "new_tok"})
            mode = stat.S_IMODE(os.stat(self.store_path).st_mode)
            self.assertEqual(mode, 0o600)
            # 新进程视角：重新加载模块并走 main()，环境变量里仍是旧令牌，
            # 构建账号时应优先取 sidecar 的新令牌
            mod2 = load_aliyunpan("aliyunpan_store_rotate_fresh")
            self._run_main(mod2)
        self.assertEqual(len(_RecordingAliYun.instances), 1)
        self.assertEqual(_RecordingAliYun.instances[0].name, "账号甲")
        self.assertEqual(_RecordingAliYun.instances[0].refresh_token, "new_tok")

    def test_missing_refresh_token_in_response_keeps_old_and_skips_write(self):
        with self._env():
            mod = load_aliyunpan("aliyunpan_store_missing_field")
            client = mod.ALiYun("账号甲", "old_tok")
            client.session = _FakeSession({"access_token": "acc"})  # 响应缺 refresh_token
            with self.assertLogs(mod.logger, level="WARNING") as cm:
                ok = client._refresh_access_token()
        self.assertTrue(ok, "拿到 access_token 即应视为刷新成功")
        self.assertEqual(client.refresh_token, "old_tok", "响应缺字段时必须保留旧令牌")
        self.assertFalse(os.path.exists(self.store_path), "响应缺字段时不应写回 sidecar")
        self.assertTrue(any("保留当前令牌" in line for line in cm.output))

    def test_save_failure_does_not_break_flow_and_never_logs_token(self):
        bad_path = os.path.join(self._tmpdir.name, "no_such_dir", "tokens.json")
        with mock.patch.dict(os.environ, {"ALIYUNPAN_TOKEN_STORE": bad_path}):
            mod = load_aliyunpan("aliyunpan_store_save_fail")
            client = mod.ALiYun("账号甲", "old_tok")
            client.session = _FakeSession({"access_token": "acc", "refresh_token": "new_tok_secret"})
            with self.assertLogs(mod.logger, level="ERROR") as cm:
                ok = client._refresh_access_token()  # 写回失败不应抛错
        self.assertTrue(ok, "持久化失败不能影响本次签到主流程")
        self.assertEqual(client.refresh_token, "new_tok_secret")
        joined = "\n".join(cm.output)
        self.assertIn("持久化失败", joined)
        self.assertNotIn("new_tok_secret", joined, "日志绝不能包含令牌原文")
        self.assertNotIn("old_tok", joined, "日志绝不能包含令牌原文")

    def test_dual_accounts_only_target_entry_updated(self):
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump({"账号甲": "tok_a_old", "账号乙": "tok_b"}, f)
        with self._env():
            mod = load_aliyunpan("aliyunpan_store_dual")
            client = mod.ALiYun("账号甲", "tok_a_old")
            client.session = _FakeSession({"access_token": "acc", "refresh_token": "tok_a_new"})
            self.assertTrue(client._refresh_access_token())
        self.assertEqual(self._read_store(), {"账号甲": "tok_a_new", "账号乙": "tok_b"})

    def test_no_sidecar_env_only_behavior_unchanged(self):
        with self._env("tok1#账号甲 & tok2#账号乙"):
            mod = load_aliyunpan("aliyunpan_store_absent")
            self.assertEqual(mod._load_token_store(), {})
            self._run_main(mod)
        tokens = {i.name: i.refresh_token for i in _RecordingAliYun.instances}
        self.assertEqual(tokens, {"账号甲": "tok1", "账号乙": "tok2"})
        self.assertFalse(os.path.exists(self.store_path),
                         "未发生刷新时不应生成 sidecar 文件")


if __name__ == "__main__":
    unittest.main()

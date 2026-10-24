#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aliyunpan.py 通知逻辑回归测试（全程 mock，不调用真实签到/真实通知服务）。

覆盖场景：
1. notify 正常发送：send_notify() 必须真正调用 notify.send(title, content)；
2. notify 模块缺失：降级为仅打印预览，不抛错、返回 False；
3. notify.send 抛错：异常被捕获记录，不向外传播、返回 False；
4. main() 多账号聚合：所有账号报告合并为一条通知，只发送一次；
5. 空报告：无有效账号时不发送通知；未配置环境变量时直接返回不发送。

运行：python3 -m unittest test_aliyunpan_notify -v（在本目录下）
"""

import importlib.util
import os
import sys
import types
import unittest
from unittest import mock

SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aliyunpan.py")


def load_aliyunpan(module_name):
    """以独立模块名加载 aliyunpan.py，避免测试间状态串扰。"""
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_fake_notify(send_impl):
    fake = types.ModuleType("notify")
    fake.send = send_impl
    return fake


class TestSendNotify(unittest.TestCase):
    def test_notify_send_actually_called(self):
        calls = []
        fake = make_fake_notify(lambda title, content: calls.append((title, content)))
        with mock.patch.dict(sys.modules, {"notify": fake}):
            mod = load_aliyunpan("aliyunpan_case_ok")
            result = mod.send_notify("标题A", "内容B")
        self.assertTrue(result)
        self.assertEqual(calls, [("标题A", "内容B")])

    def test_notify_missing_degrades_to_print(self):
        # sys.modules['notify'] = None 会使 `from notify import send` 抛 ImportError
        with mock.patch.dict(sys.modules, {"notify": None}):
            mod = load_aliyunpan("aliyunpan_case_missing")
            with self.assertLogs(mod.logger, level="WARNING") as cm:
                result = mod.send_notify("标题", "内容")
        self.assertFalse(result)
        self.assertTrue(any("未找到 notify 模块" in line for line in cm.output))

    def test_notify_send_raises_is_caught(self):
        def boom(title, content):
            raise RuntimeError("push gateway down")

        fake = make_fake_notify(boom)
        with mock.patch.dict(sys.modules, {"notify": fake}):
            mod = load_aliyunpan("aliyunpan_case_raise")
            with self.assertLogs(mod.logger, level="ERROR") as cm:
                result = mod.send_notify("标题", "内容")  # 不应抛错
        self.assertFalse(result)
        self.assertTrue(any("通知发送失败" in line for line in cm.output))


class _FakeAliYun:
    """替代真实 ALiYun 类：run() 只返回固定报告，绝不发网络请求。"""

    def __init__(self, name, refresh_token):
        self.name = name

    def run(self):
        return f"【{self.name}】签到成功（mock）"


class TestMainAggregation(unittest.TestCase):
    def _run_main(self, mod, env_value):
        with mock.patch.dict(os.environ, {"ALIYUN_ACCOUNTS": env_value}), \
             mock.patch.object(mod, "ALiYun", _FakeAliYun), \
             mock.patch("time.sleep", lambda *_a, **_k: None), \
             mock.patch("random.randint", lambda a, b: 0):
            mod.main()

    def test_main_sends_one_aggregated_notification(self):
        calls = []
        fake = make_fake_notify(lambda title, content: calls.append((title, content)))
        with mock.patch.dict(sys.modules, {"notify": fake}):
            mod = load_aliyunpan("aliyunpan_case_main")
            self._run_main(mod, "tok1#账号甲 & tok2#账号乙")
        self.assertEqual(len(calls), 1, "多账号应聚合为一条通知，只发送一次")
        title, content = calls[0]
        self.assertEqual(title, "阿里云盘签到报告")
        self.assertIn("账号甲", content)
        self.assertIn("账号乙", content)

    def test_main_empty_report_sends_nothing(self):
        calls = []
        fake = make_fake_notify(lambda title, content: calls.append((title, content)))
        with mock.patch.dict(sys.modules, {"notify": fake}):
            mod = load_aliyunpan("aliyunpan_case_empty")
            self._run_main(mod, "&&&")  # 无任何有效账号 → 报告为空
        self.assertEqual(calls, [])

    def test_main_without_env_sends_nothing(self):
        calls = []
        fake = make_fake_notify(lambda title, content: calls.append((title, content)))
        with mock.patch.dict(sys.modules, {"notify": fake}):
            mod = load_aliyunpan("aliyunpan_case_noenv")
            with mock.patch.dict(os.environ, {}, clear=True):
                mod.main()
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()

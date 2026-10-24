#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new Env('阿里云盘签到');
cron: 10 6,18 * * *

环境变量说明:
变量名: ALIYUN_ACCOUNTS
格式: refresh_token#备注名 & refresh_token2#备注名2
提示: 多个账号用 & 或 换行 分隔；内部参数用 # 分隔。
进入网页端阿里云盘，按 F12 打开开发者工具，打开控制台输入JSON.parse(localStorage.getItem("token")).refresh_token 然后拼接#备注名即可，例如：

刷新令牌持久化说明:
服务端轮换 refresh_token 后，脚本会把新令牌写回脚本同目录的 .aliyunpan_tokens.json（权限 0600），
下次运行优先使用该文件中的最新令牌，环境变量只作首次引导；可用环境变量 ALIYUNPAN_TOKEN_STORE 覆盖该文件路径。
部署时请确保脚本目录可写（青龙环境把该文件放在脚本目录即可）。
"""

import json
import os
import re
import time
import logging
import requests
import random
from typing import Dict

# ==================== 日志配置 ====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AliYun")

# ==================== 刷新令牌持久化（sidecar 文件） ====================
def _token_store_path() -> str:
    """sidecar 文件路径：默认脚本同目录，可用环境变量 ALIYUNPAN_TOKEN_STORE 覆盖。"""
    override = os.getenv("ALIYUNPAN_TOKEN_STORE", "").strip()
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".aliyunpan_tokens.json")


def _load_token_store() -> Dict[str, str]:
    """读取 sidecar 中保存的最新 refresh_token（结构为 {备注名: refresh_token}）。

    文件不存在返回空映射；文件损坏/格式异常时记录 warning 并返回空映射（回退到环境变量）。
    """
    path = _token_store_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.warning(f"读取令牌持久化文件失败（将回退到环境变量）: {e}")
        return {}
    if not isinstance(data, dict):
        logger.warning("令牌持久化文件格式异常（将回退到环境变量）")
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, str) and v}


def _save_token(name: str, refresh_token: str) -> bool:
    """把某账号轮换后的新 refresh_token 原子写回 sidecar（同目录临时文件 + rename，权限 0600）。

    只更新该账号条目；与已存值相同时直接视为成功。任何失败只记录 error 日志并返回 False，
    绝不向上抛错中断签到主流程。注意：日志中绝不输出令牌原文或其片段。
    """
    path = _token_store_path()
    try:
        store = _load_token_store()
        if store.get(name) == refresh_token:
            return True
        store[name] = refresh_token
        tmp_path = f"{path}.tmp{os.getpid()}"
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(store, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return True
    except Exception as e:
        logger.error(f"[{name}] 刷新令牌持久化失败（本次签到不受影响，但下次运行可能仍使用旧令牌）: {e}")
        return False


# ==================== 核心逻辑 ====================
class ALiYun:
    def __init__(self, name: str, refresh_token: str):
        self.session = requests.Session()
        self.name = name
        self.refresh_token = refresh_token
        self.access_token = ""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 AlphaDrive/3.0.0",
            "Content-Type": "application/json; charset=utf-8"
        }

    def _refresh_access_token(self) -> bool:
        """刷新 access_token；服务端若轮换了 refresh_token，同步写回 sidecar 持久化供下次运行使用。"""
        url = 'https://auth.aliyundrive.com/v2/account/token'
        payload = {'grant_type': 'refresh_token', 'refresh_token': self.refresh_token}
        try:
            res = self.session.post(url, json=payload, timeout=10).json()
            if 'access_token' in res:
                self.access_token = res['access_token']
                new_refresh_token = res.get('refresh_token')
                if new_refresh_token:
                    self.refresh_token = new_refresh_token
                    # 写回 sidecar 持久化；失败只大声告警，不影响本次签到
                    _save_token(self.name, new_refresh_token)
                else:
                    logger.warning(f"[{self.name}] 刷新响应未返回新的 refresh_token，保留当前令牌")
                return True
            logger.error(f"[{self.name}] 刷新 Token 失败: {res.get('message', '未知错误')}")
            return False
        except Exception as e:
            logger.error(f"[{self.name}] 刷新请求异常: {e}")
            return False

    def check_in(self) -> Dict:
        """执行签到"""
        url = 'https://member.aliyundrive.com/v1/activity/sign_in_list'
        headers = {**self.headers, "Authorization": f"Bearer {self.access_token}"}
        try:
            res = self.session.post(url, params={'_rx-s': 'mobile'}, json={'isReward': False}, headers=headers, timeout=10).json()
            return res
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_reward(self, day: int) -> str:
        """领取奖励"""
        url = 'https://member.aliyundrive.com/v1/activity/sign_in_reward'
        headers = {**self.headers, "Authorization": f"Bearer {self.access_token}"}
        try:
            res = self.session.post(url, params={'_rx-s': 'mobile'}, json={'signInDay': day}, headers=headers, timeout=10).json()
            return res.get('result', {}).get('notice', res.get('message', '未获取到奖励明细'))
        except Exception:
            return "奖励领取请求异常"

    def get_capacity(self) -> str:
        """查询容量"""
        def fmt(s): return f"{s/1024/1024/1024:.2f} GB" if s > 0 else "0 GB"
        url = 'https://api.aliyundrive.com/adrive/v1/user/driveCapacityDetails'
        headers = {**self.headers, "Authorization": f"Bearer {self.access_token}"}
        try:
            res = self.session.post(url, json={}, headers=headers, timeout=10).json()
            return (f"总空间: {fmt(res.get('drive_total_size', 0))}\n"
                    f"已用空间: {fmt(res.get('drive_used_size', 0))}")
        except: return "容量查询失败"

    def run(self):
        logger.info(f"--- 账号 [{self.name}] 开始签到 ---")
        if not self._refresh_access_token():
            return f"[{self.name}] ❌ 登录失效"

        res = self.check_in()
        if not res.get('success'):
            return f"[{self.name}] ❌ 签到失败: {res.get('message')}"

        count = res.get('result', {}).get('signInCount', 0)
        reward_info = self.get_reward(count)
        cap_info = self.get_capacity()

        msg = (f"【{self.name}】签到成功！\n"
               f"本月累计签到: {count} 天\n"
               f"本次奖励: {reward_info}\n"
               f"{cap_info}")
        return msg

# ==================== 通知逻辑 ====================
def send_notify(title, content):
    """发送通知：调用 notify.py 的 send() 真正推送。

    - notify 模块不存在时降级为仅打印预览，并明确记录日志；
    - 推送过程抛错时只记录错误并返回 False，绝不影响签到主流程结果；
    - 返回 True 表示已调用推送入口，False 表示降级或失败。
    """
    try:
        from notify import send
    except ImportError:
        logger.warning("未找到 notify 模块，降级为仅打印通知内容，不实际推送")
        logger.info("\n--- 通知预览 ---\n" + title + "\n" + content)
        return False
    try:
        send(title, content)
        return True
    except Exception as e:
        logger.error(f"通知发送失败（不影响签到结果）: {e}")
        return False

# ==================== 主入口 ====================
def main():
    raw_conf = os.getenv("ALIYUN_ACCOUNTS", "")
    if not raw_conf:
        logger.error("未找到环境变量 ALIYUN_ACCOUNTS")
        return

    # 按 & 或 换行 分隔账号
    account_list = re.split(r'[&\n]+', raw_conf.strip())
    # sidecar 中保存的是服务端轮换后的最新令牌，优先于环境变量（环境变量只作首次引导）
    token_store = _load_token_store()
    final_reports = []

    for idx, acc_str in enumerate(account_list):
        if not acc_str.strip(): continue

        # 按 # 分隔 token 和 备注
        parts = acc_str.split('#')
        token = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 else f"账号{idx+1}"

        token = token_store.get(name) or token

        if not token:
            logger.warning(f"账号 {name} 缺少 refresh_token，跳过")
            continue

        client = ALiYun(name, token)
        try:
            report = client.run()
            final_reports.append(report)
        except Exception as e:
            logger.error(f"运行异常: {e}")
            final_reports.append(f"[{name}] 运行发生异常")
        
        # 账号间随机延迟
        if idx < len(account_list) - 1:
            time.sleep(random.randint(3, 8))

    if final_reports:
        title = "阿里云盘签到报告"
        content = "\n" + "="*20 + "\n" + "\n\n".join(final_reports)
        print(title, content)
        # 多账号聚合为一条通知统一发送，不逐账号推送
        send_notify(title, content)

if __name__ == "__main__":
    main()
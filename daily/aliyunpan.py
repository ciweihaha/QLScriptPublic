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
损坏处理：sidecar 损坏（JSON 解析失败或顶层非 dict）时隔离为同目录 .aliyunpan_tokens.json.corrupt-<时间戳> 并拒绝全量覆盖，需人工处理；
写回时持同目录 .aliyunpan_tokens.lock 独占锁（10 秒超时），锁内重新加载合并；入口处清理超过 1 天的同名前缀临时文件，临时文件权限保持 0600。
"""

import json
import os
import re
import time
import logging
import requests
import random
from typing import Dict, Tuple

try:
    import fcntl
except ImportError:  # Windows 等不支持 fcntl 的环境，写回时降级为无锁行为
    fcntl = None

# ==================== 日志配置 ====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AliYun")

# ==================== 刷新令牌持久化（sidecar 文件） ====================
# 本进程内一旦检测到 sidecar 损坏即置位：即使隔离改名后文件已不存在，
# 同一进程后续的写回也不得以空映射覆盖，必须等人工处理。
_TOKEN_STORE_CORRUPT = False
_TOKEN_STORE_CORRUPT_PATH = ""


def _token_store_path() -> str:
    """sidecar 文件路径：默认脚本同目录，可用环境变量 ALIYUNPAN_TOKEN_STORE 覆盖。"""
    override = os.getenv("ALIYUNPAN_TOKEN_STORE", "").strip()
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".aliyunpan_tokens.json")


def _quarantine_corrupt_store(path: str) -> str:
    """把损坏的 sidecar 改名隔离，返回隔离路径；隔离失败返回空串。"""
    global _TOKEN_STORE_CORRUPT_PATH
    directory = os.path.dirname(path) or "."
    base = os.path.basename(path)
    stamp = time.strftime("%Y%m%d%H%M%S")
    corrupt_path = os.path.join(directory, f"{base}.corrupt-{stamp}")
    if os.path.exists(corrupt_path):
        corrupt_path = os.path.join(directory, f"{base}.corrupt-{stamp}-{os.getpid()}")
    try:
        os.replace(path, corrupt_path)
        _TOKEN_STORE_CORRUPT_PATH = corrupt_path
        return corrupt_path
    except OSError as e:
        logger.error(f"隔离损坏的令牌持久化文件失败（请人工处理）: {e}")
        return ""


def _load_token_store_with_dirty() -> Tuple[Dict[str, str], bool]:
    """读取 sidecar 中保存的最新 refresh_token（结构为 {备注名: refresh_token}），返回（映射，是否损坏）。

    文件不存在返回空映射且不标记损坏；JSON 解析失败或顶层非 dict 时把原文件改名隔离为
    同目录 .aliyunpan_tokens.json.corrupt-<时间戳>（保留证据），返回空映射（回退到环境变量）
    并标记为脏；其他读取失败同样标记为脏，避免用未知内容上的空映射覆盖。
    """
    global _TOKEN_STORE_CORRUPT
    path = _token_store_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}, False
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        _TOKEN_STORE_CORRUPT = True
        corrupt_path = _quarantine_corrupt_store(path)
        logger.error(f"令牌持久化文件已损坏（JSON 解析失败），已隔离为 {corrupt_path or path}，将回退到环境变量并拒绝后续全量覆盖，请人工处理: {e}")
        return {}, True
    except Exception as e:
        _TOKEN_STORE_CORRUPT = True
        logger.error(f"读取令牌持久化文件失败（将回退到环境变量并拒绝后续全量覆盖，请人工处理）: {e}")
        return {}, True
    if not isinstance(data, dict):
        _TOKEN_STORE_CORRUPT = True
        corrupt_path = _quarantine_corrupt_store(path)
        logger.error(f"令牌持久化文件已损坏（顶层非 dict），已隔离为 {corrupt_path or path}，将回退到环境变量并拒绝后续全量覆盖，请人工处理")
        return {}, True
    return {str(k): v for k, v in data.items() if isinstance(v, str) and v}, False


def _load_token_store() -> Dict[str, str]:
    """读取 sidecar 中保存的最新 refresh_token（结构为 {备注名: refresh_token}）。

    兼容旧签名：只返回映射。损坏处理见 _load_token_store_with_dirty；需要脏标记的调用方请用后者。
    """
    store, _dirty = _load_token_store_with_dirty()
    return store


def _cleanup_stale_token_tmp_files(path: str, max_age_seconds: int = 86400) -> None:
    """清理超过 1 天的同名前缀临时文件。

    只删 <原名>.tmp*（当前写回产生的临时文件即 f"{path}.tmp{pid}"；自定义路径无前导点时
    也兼容 .<原名>.tmp*），避免误删其他文件；清理失败静默跳过，不影响签到。
    """
    directory = os.path.dirname(path) or "."
    base = os.path.basename(path)
    prefixes = {f"{base}.tmp"}
    if not base.startswith("."):
        prefixes.add(f".{base}.tmp")
    try:
        entries = os.listdir(directory)
    except OSError:
        return
    now = time.time()
    for entry in entries:
        if not any(entry.startswith(prefix) for prefix in prefixes):
            continue
        full = os.path.join(directory, entry)
        try:
            if not os.path.isfile(full):
                continue
            if now - os.path.getmtime(full) > max_age_seconds:
                os.unlink(full)
        except OSError:
            continue


def _save_token(name: str, refresh_token: str) -> bool:
    """把某账号轮换后的新 refresh_token 写回 sidecar（同目录临时文件 + rename，权限 0600）。

    只更新该账号条目；写回前对同目录 .aliyunpan_tokens.lock 做 fcntl.flock 独占锁，锁内重新
    加载、合并、写回、解锁（os.replace 只保证单文件替换原子，不保证读-改-写序列原子）。
    10 秒内未获锁则放弃写回并记 error；flock 不可用时捕获异常并降级为当前无锁行为（记 warning）。
    sidecar 已标记损坏时拒绝全量覆盖并记 error，要求人工处理：此时加载结果即使为空 dict，
    也不得以“与已存值相同直接返回”或空映射覆盖为由写回。任何失败只记录日志并返回 False，
    绝不向上抛错中断签到主流程。注意：日志中绝不输出令牌原文或其片段。
    """
    path = _token_store_path()
    _cleanup_stale_token_tmp_files(path)
    lock_file = None
    locked = False
    try:
        if fcntl is not None:
            lock_path = os.path.join(os.path.dirname(path) or ".", ".aliyunpan_tokens.lock")
            try:
                lock_file = open(lock_path, "a+")
                deadline = time.monotonic() + 10
                while True:
                    try:
                        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        locked = True
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            logger.error(f"[{name}] 刷新令牌持久化失败：10 秒内未获得 sidecar 写锁，放弃写回（本次签到不受影响）")
                            return False
                        time.sleep(0.1)
            except OSError as e:
                # 锁本身不可用（如文件系统不支持 flock）时降级为当前无锁行为，避免锁拖垮签到。
                logger.warning(f"[{name}] sidecar 写锁不可用，降级为无锁写回: {e}")
                if lock_file is not None:
                    try:
                        lock_file.close()
                    except OSError:
                        pass
                    lock_file = None
        store, dirty = _load_token_store_with_dirty()
        if dirty or _TOKEN_STORE_CORRUPT:
            logger.error(f"[{name}] 刷新令牌持久化被拒绝：sidecar 已损坏（隔离文件见上文日志），需人工处理，拒绝全量覆盖")
            return False
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
    finally:
        if locked and lock_file is not None:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
            except Exception:
                pass
        if lock_file is not None:
            try:
                lock_file.close()
            except OSError:
                pass


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

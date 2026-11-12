#!/usr/bin/env python3
# _*_ coding:utf-8 _*_
import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

import requests

# 原先的 print 函数和主线程的锁
_print = print
mutex = threading.Lock()


# 定义新的 print 函数
def print(text, *args, **kw):
    """
    使输出有序进行，不出现多线程同一时间输出导致错乱的问题。
    """
    with mutex:
        _print(text, *args, **kw)


# 通知服务
# fmt: off
# 注释中的“例”均为占位示意，非真实凭证；真实凭证一律从环境变量读取，push_config 默认值均为空。
push_config = {
    'HITOKOTO': True,                  # 启用一言（随机句子）

    'BARK_PUSH': '',                    # bark IP 或设备码，例：https://api.day.app/DxHcxxxxxRxxxxxxcm/
    'BARK_ARCHIVE': '',                 # bark 推送是否存档
    'BARK_GROUP': '',                   # bark 推送分组
    'BARK_SOUND': '',                   # bark 推送声音
    'BARK_ICON': '',                    # bark 推送图标
    'BARK_LEVEL': '',                   # bark 推送时效性
    'BARK_URL': '',                     # bark 推送跳转URL

    'CONSOLE': False,                    # 控制台输出

    'DD_BOT_SECRET': '',                # 钉钉机器人的 DD_BOT_SECRET
    'DD_BOT_TOKEN': '',                 # 钉钉机器人的 DD_BOT_TOKEN

    'FSKEY': '',                        # 飞书机器人的 FSKEY
    'FSSECRET': '',                     # 飞书机器人的 FSSECRET，对应安全设置里的签名校验密钥

    'GOBOT_URL': '',                    # go-cqhttp
                                        # 推送到个人QQ：http://127.0.0.1/send_private_msg
                                        # 群：http://127.0.0.1/send_group_msg
    'GOBOT_QQ': '',                     # go-cqhttp 的推送群或用户
                                        # GOBOT_URL 设置 /send_private_msg 时填入 user_id=个人QQ
                                        #               /send_group_msg   时填入 group_id=QQ群
    'GOBOT_TOKEN': '',                  # go-cqhttp 的 access_token

    'GOTIFY_URL': '',                   # gotify地址,如https://push.example.de:8080
    'GOTIFY_TOKEN': '',                 # gotify的消息应用token
    'GOTIFY_PRIORITY': 0,               # 推送消息优先级,默认为0

    'IGOT_PUSH_KEY': '',                # iGot 聚合推送的 IGOT_PUSH_KEY

    'PUSH_KEY': '',                     # server 酱的 PUSH_KEY，兼容旧版与 Turbo 版

    'DEER_KEY': '',                     # PushDeer 的 PUSHDEER_KEY
    'DEER_URL': '',                     # PushDeer 的 PUSHDEER_URL

    'CHAT_URL': '',                     # synology chat url
    'CHAT_TOKEN': '',                   # synology chat token

    'PUSH_PLUS_TOKEN': '',              # pushplus 推送的用户令牌
    'PUSH_PLUS_USER': '',               # pushplus 推送的群组编码
    'PUSH_PLUS_TEMPLATE': 'html',       # pushplus 发送模板，支持html,txt,json,markdown,cloudMonitor,jenkins,route,pay
    'PUSH_PLUS_CHANNEL': 'wechat',      # pushplus 发送渠道，支持wechat,webhook,cp,mail,sms
    'PUSH_PLUS_WEBHOOK': '',            # pushplus webhook编码，可在pushplus公众号上扩展配置出更多渠道
    'PUSH_PLUS_CALLBACKURL': '',        # pushplus 发送结果回调地址，会把推送最终结果通知到这个地址上
    'PUSH_PLUS_TO': '',                 # pushplus 好友令牌，微信公众号渠道填写好友令牌，企业微信渠道填写企业微信用户id

    'WE_PLUS_BOT_TOKEN': '',            # 微加机器人的用户令牌
    'WE_PLUS_BOT_RECEIVER': '',         # 微加机器人的消息接收者
    'WE_PLUS_BOT_VERSION': 'pro',          # 微加机器人的调用版本

    'QMSG_KEY': '',                     # qmsg 酱的 QMSG_KEY
    'QMSG_TYPE': '',                    # qmsg 酱的 QMSG_TYPE

    'QYWX_ORIGIN': '',                  # 企业微信代理地址

    'QYWX_AM': '',                      # 企业微信应用

    'QYWX_KEY': '',                     # 企业微信机器人

    'TG_BOT_TOKEN': '',                 # tg 机器人的 TG_BOT_TOKEN，例：<YOUR_BOT_TOKEN>（占位符，非真实值）
    'TG_USER_ID': '',                   # tg 机器人的 TG_USER_ID，例：<YOUR_USER_ID>（占位符，非真实值）
    'TG_API_HOST': '',                  # tg 代理 api
    'TG_PROXY_AUTH': '',                # tg 代理认证参数
    'TG_PROXY_HOST': '',                # tg 机器人的 TG_PROXY_HOST
    'TG_PROXY_PORT': '',                # tg 机器人的 TG_PROXY_PORT

    'AIBOTK_KEY': '',                   # 智能微秘书 个人中心的apikey 文档地址：http://wechat.aibotk.com/docs/about
    'AIBOTK_TYPE': '',                  # 智能微秘书 发送目标 room 或 contact
    'AIBOTK_NAME': '',                  # 智能微秘书  发送群名 或者好友昵称和type要对应好

    'SMTP_SERVER': '',                  # SMTP 发送邮件服务器，形如 smtp.exmail.qq.com:465
    'SMTP_SSL': 'false',                # SMTP 发送邮件服务器是否使用 SSL，填写 true 或 false
    'SMTP_EMAIL': '',                   # SMTP 收发件邮箱，通知将会由自己发给自己
    'SMTP_PASSWORD': '',                # SMTP 登录密码，也可能为特殊口令，视具体邮件服务商说明而定
    'SMTP_NAME': '',                    # SMTP 收发件人姓名，可随意填写

    'PUSHME_KEY': '',                   # PushMe 的 PUSHME_KEY
    'PUSHME_URL': '',                   # PushMe 的 PUSHME_URL

    'CHRONOCAT_QQ': '',                 # qq号
    'CHRONOCAT_TOKEN': '',              # CHRONOCAT 的token
    'CHRONOCAT_URL': '',                # CHRONOCAT的url地址

    'WEBHOOK_URL': '',                  # 自定义通知 请求地址
    'WEBHOOK_BODY': '',                 # 自定义通知 请求体
    'WEBHOOK_HEADERS': '',              # 自定义通知 请求头
    'WEBHOOK_METHOD': '',               # 自定义通知 请求方法
    'WEBHOOK_CONTENT_TYPE': '',         # 自定义通知 content-type

    'NTFY_URL': '',                     # ntfy地址,如https://ntfy.sh
    'NTFY_TOPIC': '',                   # ntfy的消息应用topic
    'NTFY_PRIORITY':'3',                # 推送消息优先级,默认为3
    'NTFY_TOKEN': '',                   # 推送token,可选
    'NTFY_USERNAME': '',                # 推送用户名称,可选
    'NTFY_PASSWORD': '',                # 推送用户密码,可选
    'NTFY_ACTIONS': '',                 # 推送用户动作,可选

    'WXPUSHER_APP_TOKEN': '',           # wxpusher 的 appToken 官方文档: https://wxpusher.zjiecode.com/docs/ 管理后台: https://wxpusher.zjiecode.com/admin/
    'WXPUSHER_TOPIC_IDS': '',           # wxpusher 的 主题ID，多个用英文分号;分隔 topic_ids 与 uids 至少配置一个才行
    'WXPUSHER_UIDS': '',                # wxpusher 的 用户ID，多个用英文分号;分隔 topic_ids 与 uids 至少配置一个才行
}
# fmt: on

for k in push_config:
    if os.getenv(k):
        v = os.getenv(k)
        push_config[k] = v


def bark(title: str, content: str) -> None:
    """
    使用 bark 推送消息。
    """
    if not push_config.get("BARK_PUSH"):
        return
    print("bark 服务启动")

    if push_config.get("BARK_PUSH").startswith("http"):
        url = f'{push_config.get("BARK_PUSH")}'
    else:
        url = f'https://api.day.app/{push_config.get("BARK_PUSH")}'

    bark_params = {
        "BARK_ARCHIVE": "isArchive",
        "BARK_GROUP": "group",
        "BARK_SOUND": "sound",
        "BARK_ICON": "icon",
        "BARK_LEVEL": "level",
        "BARK_URL": "url",
    }
    data = {
        "title": title,
        "body": content,
    }
    for pair in filter(
        lambda pairs: pairs[0].startswith("BARK_")
        and pairs[0] != "BARK_PUSH"
        and pairs[1]
        and bark_params.get(pairs[0]),
        push_config.items(),
    ):
        data[bark_params.get(pair[0])] = pair[1]
    headers = {"Content-Type": "application/json;charset=utf-8"}
    response = requests.post(
        url=url, data=json.dumps(data), headers=headers, timeout=15
    ).json()

    if response.get("code") == 200:
        print("bark 推送成功！")
    else:
        print("bark 推送失败！")


def console(title: str, content: str) -> None:
    """
    使用 控制台 推送消息。
    """
    print(f"{title}\n\n{content}")


def dingding_bot(title: str, content: str) -> None:
    """
    使用 钉钉机器人 推送消息。
    """
    if not push_config.get("DD_BOT_SECRET") or not push_config.get("DD_BOT_TOKEN"):
        return
    print("钉钉机器人 服务启动")

    timestamp = str(round(time.time() * 1000))
    secret_enc = push_config.get("DD_BOT_SECRET").encode("utf-8")
    string_to_sign = "{}\n{}".format(timestamp, push_config.get("DD_BOT_SECRET"))
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(
        secret_enc, string_to_sign_enc, digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    url = f'https://oapi.dingtalk.com/robot/send?access_token={push_config.get("DD_BOT_TOKEN")}&timestamp={timestamp}&sign={sign}'
    headers = {"Content-Type": "application/json;charset=utf-8"}
    data = {"msgtype": "text", "text": {"content": f"{title}\n\n{content}"}}
    response = requests.post(
        url=url, data=json.dumps(data), headers=headers, timeout=15
    ).json()

    if response.get("errcode") == 0:
        print("钉钉机器人 推送成功！")
    else:
        print("钉钉机器人 推送失败！")


def feishu_bot(title: str, content: str) -> None:
    """
    使用 飞书机器人 推送消息。
    """
    if not push_config.get("FSKEY"):
        return
    print("飞书 服务启动")

    url = f'https://open.feishu.cn/open-apis/bot/v2/hook/{push_config.get("FSKEY")}'
    data = {"msg_type": "text", "content": {"text": f"{title}\n\n{content}"}}

    # Add signature if secret is provided
    # Note: Feishu's signature algorithm uses timestamp+"\n"+secret as the HMAC key
    # and signs an empty message, which differs from typical HMAC usage
    if push_config.get("FSSECRET"):
        timestamp = str(int(time.time()))
        string_to_sign = f'{timestamp}\n{push_config.get("FSSECRET")}'
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        data["timestamp"] = timestamp
        data["sign"] = sign

    # 深查第 7 轮：补齐第 5 轮登记、第 6 轮只修了 SMTP 的 18 处无 timeout
    # requests 调用（本文件 feishu/gotify/iGot/serverJ/pushdeer/chat/
    # pushplus/weplus/qmsg/WeCom×3/telegram/aibotk/pushme/chronocat/
    # ntfy/wxpusher；双生文件同改）。无 timeout 时上游挂起会卡住通道
    # 线程直至 send() 的 60 秒总预算耗尽；统一补 timeout=15（仓内惯用值），
    # 只加超时，不改 URL、参数与成功判定。
    response = requests.post(url, data=json.dumps(data), timeout=15).json()

    if response.get("StatusCode") == 0 or response.get("code") == 0:
        print("飞书 推送成功！")
    else:
        print("飞书 推送失败！错误信息如下：\n", response)


def go_cqhttp(title: str, content: str) -> None:
    """
    使用 go_cqhttp 推送消息。
    """
    if not push_config.get("GOBOT_URL") or not push_config.get("GOBOT_QQ"):
        return
    print("go-cqhttp 服务启动")

    # 深查第 10 轮：message 值做 URL 编码（双生文件同改）。原先标题/内容
    # 直接拼进 query：含 & 时消息在第一个 & 处截断（实测标题"签到&B"只剩
    # "标题:签到"），含 =/# /空格时还会串改参数或丢进 fragment。
    # 只编码 message 这一个值（quote_plus：空格→+、换行→%0A、&/=# 等按
    # UTF-8 百分号编码，服务端标准解析还原）；access_token 与 GOBOT_QQ
    # 的拼接形态不动（第 1 轮已声明不擅自改鉴权形态）。
    message = urllib.parse.quote_plus(f"标题:{title}\n内容:{content}")
    url = f'{push_config.get("GOBOT_URL")}?access_token={push_config.get("GOBOT_TOKEN")}&{push_config.get("GOBOT_QQ")}&message={message}'
    # 深查第 1 轮：同文件 bark/dingding/wecom 等通道均用 timeout=15，
    # 本通道原先无 timeout，上游挂起时会卡住整个 notify 链，后续通道不再执行。
    # 只加 timeout，不改 URL 与鉴权形态（go-cqhttp 的 access_token 查询参数语义未验证，不擅自改 header）。
    response = requests.get(url, timeout=15).json()

    if response.get("status") == "ok":
        print("go-cqhttp 推送成功！")
    else:
        print("go-cqhttp 推送失败！")


def gotify(title: str, content: str) -> None:
    """
    使用 gotify 推送消息。
    """
    if not push_config.get("GOTIFY_URL") or not push_config.get("GOTIFY_TOKEN"):
        return
    print("gotify 服务启动")

    url = f'{push_config.get("GOTIFY_URL")}/message?token={push_config.get("GOTIFY_TOKEN")}'
    data = {
        "title": title,
        "message": content,
        "priority": push_config.get("GOTIFY_PRIORITY"),
    }
    response = requests.post(url, data=data, timeout=15).json()

    if response.get("id"):
        print("gotify 推送成功！")
    else:
        print("gotify 推送失败！")


def iGot(title: str, content: str) -> None:
    """
    使用 iGot 推送消息。
    """
    if not push_config.get("IGOT_PUSH_KEY"):
        return
    print("iGot 服务启动")

    url = f'https://push.hellyw.com/{push_config.get("IGOT_PUSH_KEY")}'
    data = {"title": title, "content": content}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(url, data=data, headers=headers, timeout=15).json()

    if response.get("ret") == 0:
        print("iGot 推送成功！")
    else:
        print(f'iGot 推送失败！{response.get("errMsg")}')


def serverJ(title: str, content: str) -> None:
    """
    通过 serverJ 推送消息。
    """
    if not push_config.get("PUSH_KEY"):
        return
    print("serverJ 服务启动")

    data = {"text": title, "desp": content.replace("\n", "\n\n")}

    match = re.match(r"sctp(\d+)t", push_config.get("PUSH_KEY"))
    if match:
        num = match.group(1)
        url = f'https://{num}.push.ft07.com/send/{push_config.get("PUSH_KEY")}.send'
    else:
        url = f'https://sctapi.ftqq.com/{push_config.get("PUSH_KEY")}.send'

    response = requests.post(url, data=data, timeout=15).json()

    # 深查第 8 轮：失败分支直接索引改 .get()（双生文件同改；本处是第 7 轮
    # mock 验证时真实触发的点：上游回包缺 "message" 时原 response["message"]
    # 抛 KeyError，"推送失败" 永远打不出来，通道线程直接崩掉。同类还有
    # iGot errMsg、qmsg reason、aibotk error、pushplus data/msg 与各通道
    # 成功判定的 code/errcode/status/ret/ok、WeCom 的 access_token/errmsg，
    # 共 19 处——只认显式成功值，缺字段一律走失败分支，不抛错。
    # one() 的 res["hitokoto"] 在第 4 轮 try/except 内，不动。
    if response.get("errno") == 0 or response.get("code") == 0:
        print("serverJ 推送成功！")
    else:
        print(f'serverJ 推送失败！错误码：{response.get("message")}')


def pushdeer(title: str, content: str) -> None:
    """
    通过PushDeer 推送消息
    """
    if not push_config.get("DEER_KEY"):
        return
    print("PushDeer 服务启动")
    data = {
        "text": title,
        "desp": content,
        "type": "markdown",
        "pushkey": push_config.get("DEER_KEY"),
    }
    url = "https://api2.pushdeer.com/message/push"
    if push_config.get("DEER_URL"):
        url = push_config.get("DEER_URL")

    response = requests.post(url, data=data, timeout=15).json()

    # 深查第 3 轮：PushDeer 的 content 是多形态字段——成功时为 {"result": [...]}，
    # 失败时为字符串错误信息（或缺失）；原 `response.get("content").get("result")`
    # 在失败路径上先抛 AttributeError/TypeError，"推送失败" 永远打不出来。
    # 只认 dict 形态 content 下的非空 list result 为成功，其余一律走失败分支。
    content = response.get("content")
    result = content.get("result") if isinstance(content, dict) else None
    if isinstance(result, list) and len(result) > 0:
        print("PushDeer 推送成功！")
    else:
        print("PushDeer 推送失败！错误信息：", response)


def chat(title: str, content: str) -> None:
    """
    通过Chat 推送消息
    """
    if not push_config.get("CHAT_URL") or not push_config.get("CHAT_TOKEN"):
        return
    print("chat 服务启动")
    # 深查第 11 轮：payload 值做 URL 编码（双生文件同改；同类问题见第 10 轮
    # go_cqhttp）。原先 JSON 直接拼在表单体里：内容含 & 时服务端按表单
    # 解析，payload 在第一个 & 处截断（实测只剩残缺 JSON，Synology Chat
    # 侧解析失败整条丢掉）。只编码 payload 这一个值（quote_plus），
    # 字段名、CHAT_URL/TOKEN 拼接形态与 JSON 结构不动。
    data = "payload=" + urllib.parse.quote_plus(
        json.dumps({"text": title + "\n" + content})
    )
    url = push_config.get("CHAT_URL") + push_config.get("CHAT_TOKEN")
    response = requests.post(url, data=data, timeout=15)

    if response.status_code == 200:
        print("Chat 推送成功！")
    else:
        print("Chat 推送失败！错误信息：", response)


def pushplus_bot(title: str, content: str) -> None:
    """
    通过 pushplus 推送消息。
    """
    if not push_config.get("PUSH_PLUS_TOKEN"):
        return
    print("PUSHPLUS 服务启动")

    url = "https://www.pushplus.plus/send"
    data = {
        "token": push_config.get("PUSH_PLUS_TOKEN"),
        "title": title,
        "content": content,
        "topic": push_config.get("PUSH_PLUS_USER"),
        "template": push_config.get("PUSH_PLUS_TEMPLATE"),
        "channel": push_config.get("PUSH_PLUS_CHANNEL"),
        "webhook": push_config.get("PUSH_PLUS_WEBHOOK"),
        "callbackUrl": push_config.get("PUSH_PLUS_CALLBACKURL"),
        "to": push_config.get("PUSH_PLUS_TO"),
    }
    body = json.dumps(data).encode(encoding="utf-8")
    headers = {"Content-Type": "application/json"}
    response = requests.post(url=url, data=body, headers=headers, timeout=15).json()

    code = response.get("code")
    if code == 200:
        # 深查第 19 轮：成功分支 data 非字符串抛 TypeError（双生文件同改）。
        # 流水号 data 通常是字符串，但上游回数字时 `"..." + data` 直接抛
        # TypeError——推送明明成功了，成功分支自己崩掉（_run_channel 接住后
        # 只剩一行“推送异常”，用户还以为没推成功）。str() 包一层再拼接。
        print("PUSHPLUS 推送请求成功，可根据流水号查询推送结果:" + str(response.get("data") or ""))
        print(
            "注意：请求成功并不代表推送成功，如未收到消息，请到pushplus官网使用流水号查询推送最终结果"
        )
    elif code == 900 or code == 903 or code == 905 or code == 999:
        print(response.get("msg"))

    else:
        # 2026-11-05 第 2 轮：删掉明文 HTTP 非官方域名回退。原逻辑在主通道异常时
        # 把同一 body（含 PUSH_PLUS_TOKEN）原样发到 http://pushplus.hxtrip.com/send，
        # 明文且非官方，令牌外泄风险大于推送成功收益；现只报失败，不重发、不换域。
        print("PUSHPLUS 推送失败！")


def weplus_bot(title: str, content: str) -> None:
    """
    通过 微加机器人 推送消息。
    """
    if not push_config.get("WE_PLUS_BOT_TOKEN"):
        return
    print("微加机器人 服务启动")

    template = "txt"
    if len(content) > 800:
        template = "html"

    url = "https://www.weplusbot.com/send"
    data = {
        "token": push_config.get("WE_PLUS_BOT_TOKEN"),
        "title": title,
        "content": content,
        "template": template,
        "receiver": push_config.get("WE_PLUS_BOT_RECEIVER"),
        "version": push_config.get("WE_PLUS_BOT_VERSION"),
    }
    body = json.dumps(data).encode(encoding="utf-8")
    headers = {"Content-Type": "application/json"}
    response = requests.post(url=url, data=body, headers=headers, timeout=15).json()

    if response.get("code") == 200:
        print("微加机器人 推送成功！")
    else:
        print("微加机器人 推送失败！")


def qmsg_bot(title: str, content: str) -> None:
    """
    使用 qmsg 推送消息。
    """
    if not push_config.get("QMSG_KEY") or not push_config.get("QMSG_TYPE"):
        return
    print("qmsg 服务启动")

    url = f'https://qmsg.zendee.cn/{push_config.get("QMSG_TYPE")}/{push_config.get("QMSG_KEY")}'
    payload = {"msg": f'{title}\n\n{content.replace("----", "-")}'.encode("utf-8")}
    response = requests.post(url=url, params=payload, timeout=15).json()

    if response.get("code") == 0:
        print("qmsg 推送成功！")
    else:
        print(f'qmsg 推送失败！{response.get("reason")}')


def wecom_app(title: str, content: str) -> None:
    """
    通过 企业微信 APP 推送消息。
    """
    if not push_config.get("QYWX_AM"):
        return
    # 深查第 13 轮：分段后 strip（双生文件同改）。环境变量手填常带空格
    # （"corpid, secret, user, agentid"），原先直接 split，corpsecret
    # 带前导空格 " secret"，企微取 token 直接拒掉；corpid 首段不受影响、
    # touser/agentid 同理。ID 与密钥本身不含首尾空格，strip 安全。
    QYWX_AM_AY = [seg.strip() for seg in re.split(",", push_config.get("QYWX_AM"))]
    # 深查第 2 轮：原条件 `4 < len(...) > 5` 是链式比较，等价于 len > 5，
    # 1–3 段的短配置会漏过校验，随后在 QYWX_AM_AY[1]/[2]/[3] 处抛 IndexError；
    # 正确语义是只接受 4 段（无 media_id）或 5 段（含 media_id）。
    if len(QYWX_AM_AY) < 4 or len(QYWX_AM_AY) > 5:
        print("QYWX_AM 设置错误!!")
        return
    print("企业微信 APP 服务启动")

    corpid = QYWX_AM_AY[0]
    corpsecret = QYWX_AM_AY[1]
    touser = QYWX_AM_AY[2]
    agentid = QYWX_AM_AY[3]
    try:
        media_id = QYWX_AM_AY[4]
    except IndexError:
        media_id = ""
    wx = WeCom(corpid, corpsecret, agentid)
    # 如果没有配置 media_id 默认就以 text 方式发送
    if not media_id:
        message = title + "\n\n" + content
        response = wx.send_text(message, touser)
    else:
        response = wx.send_mpnews(title, content, media_id, touser)

    if response == "ok":
        print("企业微信推送成功！")
    else:
        print("企业微信推送失败！错误信息如下：\n", response)


class WeCom:
    def __init__(self, corpid, corpsecret, agentid):
        self.CORPID = corpid
        self.CORPSECRET = corpsecret
        self.AGENTID = agentid
        self.ORIGIN = "https://qyapi.weixin.qq.com"
        if push_config.get("QYWX_ORIGIN"):
            self.ORIGIN = push_config.get("QYWX_ORIGIN")

    def get_access_token(self):
        url = f"{self.ORIGIN}/cgi-bin/gettoken"
        values = {
            "corpid": self.CORPID,
            "corpsecret": self.CORPSECRET,
        }
        req = requests.post(url, params=values, timeout=15)
        data = json.loads(req.text)
        return data.get("access_token")

    def send_text(self, message, touser="@all"):
        send_url = (
            f"{self.ORIGIN}/cgi-bin/message/send?access_token={self.get_access_token()}"
        )
        send_values = {
            "touser": touser,
            "msgtype": "text",
            "agentid": self.AGENTID,
            "text": {"content": message},
            "safe": "0",
        }
        send_msges = bytes(json.dumps(send_values), "utf-8")
        respone = requests.post(send_url, send_msges, timeout=15)
        respone = respone.json()
        return respone.get("errmsg")

    def send_mpnews(self, title, message, media_id, touser="@all"):
        send_url = (
            f"{self.ORIGIN}/cgi-bin/message/send?access_token={self.get_access_token()}"
        )
        send_values = {
            "touser": touser,
            "msgtype": "mpnews",
            "agentid": self.AGENTID,
            "mpnews": {
                "articles": [
                    {
                        "title": title,
                        "thumb_media_id": media_id,
                        "author": "Author",
                        "content_source_url": "",
                        "content": message.replace("\n", "<br/>"),
                        "digest": message,
                    }
                ]
            },
        }
        send_msges = bytes(json.dumps(send_values), "utf-8")
        respone = requests.post(send_url, send_msges, timeout=15)
        respone = respone.json()
        return respone.get("errmsg")


def wecom_bot(title: str, content: str) -> None:
    """
    通过 企业微信机器人 推送消息。
    """
    if not push_config.get("QYWX_KEY"):
        return
    print("企业微信机器人服务启动")

    origin = "https://qyapi.weixin.qq.com"
    if push_config.get("QYWX_ORIGIN"):
        origin = push_config.get("QYWX_ORIGIN")

    url = f"{origin}/cgi-bin/webhook/send?key={push_config.get('QYWX_KEY')}"
    headers = {"Content-Type": "application/json;charset=utf-8"}
    data = {"msgtype": "text", "text": {"content": f"{title}\n\n{content}"}}
    response = requests.post(
        url=url, data=json.dumps(data), headers=headers, timeout=15
    ).json()

    if response.get("errcode") == 0:
        print("企业微信机器人推送成功！")
    else:
        print("企业微信机器人推送失败！")


def telegram_bot(title: str, content: str) -> None:
    """
    使用 telegram 机器人 推送消息。
    """
    if not push_config.get("TG_BOT_TOKEN") or not push_config.get("TG_USER_ID"):
        return
    print("tg 服务启动")

    if push_config.get("TG_API_HOST"):
        url = f"{push_config.get('TG_API_HOST')}/bot{push_config.get('TG_BOT_TOKEN')}/sendMessage"
    else:
        url = (
            f"https://api.telegram.org/bot{push_config.get('TG_BOT_TOKEN')}/sendMessage"
        )
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "chat_id": str(push_config.get("TG_USER_ID")),
        "text": f"{title}\n\n{content}",
        "disable_web_page_preview": "true",
    }
    proxies = None
    if push_config.get("TG_PROXY_HOST") and push_config.get("TG_PROXY_PORT"):
        # 深查第 12 轮：TG_PROXY_AUTH 未填时 push_config 里是空串 '' 而非 None，
        # 原 `is not None` 恒为真，会把 "" + "@" 拼进 host，代理变成
        # http://@host:port（空 userinfo，非法代理）且写回污染全局配置，
        # 之后每次调用都走坏代理。改判真值：只有非空认证才拼接。
        if push_config.get("TG_PROXY_AUTH") and "@" not in push_config.get(
            "TG_PROXY_HOST"
        ):
            push_config["TG_PROXY_HOST"] = (
                push_config.get("TG_PROXY_AUTH")
                + "@"
                + push_config.get("TG_PROXY_HOST")
            )
        proxyStr = "http://{}:{}".format(
            push_config.get("TG_PROXY_HOST"), push_config.get("TG_PROXY_PORT")
        )
        proxies = {"http": proxyStr, "https": proxyStr}
    response = requests.post(
        url=url, headers=headers, params=payload, proxies=proxies, timeout=15
    ).json()

    if response.get("ok"):
        print("tg 推送成功！")
    else:
        print("tg 推送失败！")


def aibotk(title: str, content: str) -> None:
    """
    使用 智能微秘书 推送消息。
    """
    if (
        not push_config.get("AIBOTK_KEY")
        or not push_config.get("AIBOTK_TYPE")
        or not push_config.get("AIBOTK_NAME")
    ):
        return
    print("智能微秘书 服务启动")

    if push_config.get("AIBOTK_TYPE") == "room":
        url = "https://api-bot.aibotk.com/openapi/v1/chat/room"
        data = {
            "apiKey": push_config.get("AIBOTK_KEY"),
            "roomName": push_config.get("AIBOTK_NAME"),
            "message": {"type": 1, "content": f"【青龙快讯】\n\n{title}\n{content}"},
        }
    else:
        url = "https://api-bot.aibotk.com/openapi/v1/chat/contact"
        data = {
            "apiKey": push_config.get("AIBOTK_KEY"),
            "name": push_config.get("AIBOTK_NAME"),
            "message": {"type": 1, "content": f"【青龙快讯】\n\n{title}\n{content}"},
        }
    body = json.dumps(data).encode(encoding="utf-8")
    headers = {"Content-Type": "application/json"}
    response = requests.post(url=url, data=body, headers=headers, timeout=15).json()
    print(response)
    if response.get("code") == 0:
        print("智能微秘书 推送成功！")
    else:
        print(f'智能微秘书 推送失败！{response.get("error")}')


def smtp(title: str, content: str) -> None:
    """
    使用 SMTP 邮件 推送消息。
    """
    if (
        not push_config.get("SMTP_SERVER")
        or not push_config.get("SMTP_SSL")
        or not push_config.get("SMTP_EMAIL")
        or not push_config.get("SMTP_PASSWORD")
        or not push_config.get("SMTP_NAME")
    ):
        return
    print("SMTP 邮件 服务启动")

    message = MIMEText(content, "plain", "utf-8")
    message["From"] = formataddr(
        (
            Header(push_config.get("SMTP_NAME"), "utf-8").encode(),
            push_config.get("SMTP_EMAIL"),
        )
    )
    message["To"] = formataddr(
        (
            Header(push_config.get("SMTP_NAME"), "utf-8").encode(),
            push_config.get("SMTP_EMAIL"),
        )
    )
    message["Subject"] = Header(title, "utf-8")

    try:
        # 深查第 6 轮：原先未传 timeout，smtplib 的 timeout 缺省走 socket 默认
        # （None = 无限阻塞），上游挂起时建连、login、发信三步任一步都可永远卡住，
        # 通道线程永不返回。这是第 5 轮登记的第 19 个挂起点（18 处 requests
        # 调用 + SMTP）。只加 timeout=15（仓内通道惯用值），不改主机名、端口
        # 与 SSL 选择语义（"host:port" 写法由 smtplib.connect 自行拆分）。
        # 深查第 18 轮：SMTP_SSL 大小写/布尔形态（双生文件同改）。原先
        # `== "true"` 精确匹配：用户写 "True"/"TRUE"、或经 kwargs 传布尔
        # True 时都被判为明文，明文连 465 这类 SSL 端口握手即失败，报错却
        # 只说“推送失败”，根因难定位。改为大小写不敏感比较（str() 包一层
        # 兼顾布尔 True）；"false"/"False"/其他值仍走明文，默认行为不变。
        smtp_server = (
            smtplib.SMTP_SSL(push_config.get("SMTP_SERVER"), timeout=15)
            if str(push_config.get("SMTP_SSL")).lower() == "true"
            else smtplib.SMTP(push_config.get("SMTP_SERVER"), timeout=15)
        )
        smtp_server.login(
            push_config.get("SMTP_EMAIL"), push_config.get("SMTP_PASSWORD")
        )
        smtp_server.sendmail(
            push_config.get("SMTP_EMAIL"),
            push_config.get("SMTP_EMAIL"),
            message.as_bytes(),
        )
        smtp_server.close()
        print("SMTP 邮件 推送成功！")
    except Exception as e:
        print(f"SMTP 邮件 推送失败！{e}")


def pushme(title: str, content: str) -> None:
    """
    使用 PushMe 推送消息。
    """
    if not push_config.get("PUSHME_KEY"):
        return
    print("PushMe 服务启动")

    url = (
        push_config.get("PUSHME_URL")
        if push_config.get("PUSHME_URL")
        else "https://push.i-i.me/"
    )
    data = {
        "push_key": push_config.get("PUSHME_KEY"),
        "title": title,
        "content": content,
        "date": push_config.get("date") if push_config.get("date") else "",
        "type": push_config.get("type") if push_config.get("type") else "",
    }
    response = requests.post(url, data=data, timeout=15)

    if response.status_code == 200 and response.text == "success":
        print("PushMe 推送成功！")
    else:
        print(f"PushMe 推送失败！{response.status_code} {response.text}")


def chronocat(title: str, content: str) -> None:
    """
    使用 CHRONOCAT 推送消息。
    """
    if (
        not push_config.get("CHRONOCAT_URL")
        or not push_config.get("CHRONOCAT_QQ")
        or not push_config.get("CHRONOCAT_TOKEN")
    ):
        return

    print("CHRONOCAT 服务启动")

    user_ids = re.findall(r"user_id=(\d+)", push_config.get("CHRONOCAT_QQ"))
    group_ids = re.findall(r"group_id=(\d+)", push_config.get("CHRONOCAT_QQ"))
    # 深查第 15 轮：CHRONOCAT_QQ 解析不到任何收件人时静默零发送（双生文件
    # 同改）。注释只写"qq号"，用户填裸 QQ 号（如 123456）时两个 findall
    # 都为空，循环一次不跑、无成功无失败、连一行日志都没有，误以为已推送。
    # 解析为空时直接点名格式并返回，不发请求。
    if not user_ids and not group_ids:
        print("CHRONOCAT_QQ 未解析到 user_id/group_id，请检查格式（例：user_id=123 group_id=456）！")
        return

    url = f'{push_config.get("CHRONOCAT_URL")}/api/message/send'
    headers = {
        "Content-Type": "application/json",
        "Authorization": f'Bearer {push_config.get("CHRONOCAT_TOKEN")}',
    }

    for chat_type, ids in [(1, user_ids), (2, group_ids)]:
        if not ids:
            continue
        for chat_id in ids:
            data = {
                "peer": {"chatType": chat_type, "peerUin": chat_id},
                "elements": [
                    {
                        "elementType": 1,
                        "textElement": {"content": f"{title}\n\n{content}"},
                    }
                ],
            }
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=15)
            # 深查第 20 轮：逐条日志只点名当条 chat_id（双生文件同改）。原先印的
            # 是整张 ids 表：配 2 个收件人时打出两行一模一样、都带 ['111', '222']
            # 的“成功”，分不清哪条真发了、哪条失败；改为当条 chat_id。
            if response.status_code == 200:
                if chat_type == 1:
                    print(f"QQ个人消息:{chat_id}推送成功！")
                else:
                    print(f"QQ群消息:{chat_id}推送成功！")
            else:
                if chat_type == 1:
                    print(f"QQ个人消息:{chat_id}推送失败！")
                else:
                    print(f"QQ群消息:{chat_id}推送失败！")


def ntfy(title: str, content: str) -> None:
    """
    通过 Ntfy 推送消息
    """

    def encode_rfc2047(text: str) -> str:
        """将文本编码为符合 RFC 2047 标准的格式"""
        encoded_bytes = base64.b64encode(text.encode("utf-8"))
        encoded_str = encoded_bytes.decode("utf-8")
        return f"=?utf-8?B?{encoded_str}?="

    if not push_config.get("NTFY_TOPIC"):
        return
    # 深查第 17 轮：缺 URL 时明示返回（双生文件同改）。原先只判 TOPIC，
    # URL 为空时拼出 "/topic" 无 scheme 地址，requests 抛 MissingSchema，
    # 每次发送都在 _run_channel 里记一条异常；有 TOPIC 无 URL 的配置本就
    # 发不出去，改为入口点名、不发请求。
    if not push_config.get("NTFY_URL"):
        print("ntfy 服务的 NTFY_URL 未设置!!")
        return
    print("ntfy 服务启动")
    priority = "3"
    if not push_config.get("NTFY_PRIORITY"):
        print("ntfy 服务的NTFY_PRIORITY 未设置!!默认设置为3")
    else:
        priority = push_config.get("NTFY_PRIORITY")

    # 使用 RFC 2047 编码 title
    encoded_title = encode_rfc2047(title)

    data = content.encode(encoding="utf-8")
    headers = {"Title": encoded_title, "Priority": priority, "Icon": "https://qn.whyour.cn/logo.png"}  # 使用编码后的 title
    if push_config.get("NTFY_TOKEN"):
        headers['Authorization'] = "Bearer " + push_config.get("NTFY_TOKEN")
    elif push_config.get("NTFY_USERNAME") and push_config.get("NTFY_PASSWORD"):
        authStr = push_config.get("NTFY_USERNAME") + ":" + push_config.get("NTFY_PASSWORD")
        headers['Authorization'] = "Basic " + base64.b64encode(authStr.encode('utf-8')).decode('utf-8')
    if push_config.get("NTFY_ACTIONS"):
        headers['Actions'] = encode_rfc2047(push_config.get("NTFY_ACTIONS"))

    url = push_config.get("NTFY_URL") + "/" + push_config.get("NTFY_TOPIC")
    response = requests.post(url, data=data, headers=headers, timeout=15)
    if response.status_code == 200:  # 使用 response.status_code 进行检查
        print("Ntfy 推送成功！")
    else:
        print("Ntfy 推送失败！错误信息：", response.text)


def wxpusher_bot(title: str, content: str) -> None:
    """
    通过 wxpusher 推送消息。
    支持的环境变量:
    - WXPUSHER_APP_TOKEN: appToken
    - WXPUSHER_TOPIC_IDS: 主题ID, 多个用英文分号;分隔
    - WXPUSHER_UIDS: 用户ID, 多个用英文分号;分隔
    """
    if not push_config.get("WXPUSHER_APP_TOKEN"):
        return

    url = "https://wxpusher.zjiecode.com/api/send/message"

    # 处理topic_ids和uids，将分号分隔的字符串转为数组
    topic_ids = []
    if push_config.get("WXPUSHER_TOPIC_IDS"):
        # 深查第 17 轮：单个非数字分段不再拖垮整通道（双生文件同改）。原先
        # 列表推导里 int() 遇非数字直接抛 ValueError，_run_channel 接住后
        # 整条 wxpusher 通道跳过——一个手误分段让全部 topic 与 uid 都收不到。
        # 改为逐段解析：数字进数组，非数字只点名该分段并跳过；全是非数字时
        # topic_ids 为空，走下文“至少设置一个”的既有分支。
        for _seg in push_config.get("WXPUSHER_TOPIC_IDS").split(";"):
            _seg = _seg.strip()
            if not _seg:
                continue
            try:
                topic_ids.append(int(_seg))
            except ValueError:
                print(f"wxpusher 的 WXPUSHER_TOPIC_IDS 含非数字分段 '{_seg}'，已跳过该分段！")

    uids = []
    if push_config.get("WXPUSHER_UIDS"):
        uids = [
            uid.strip()
            for uid in push_config.get("WXPUSHER_UIDS").split(";")
            if uid.strip()
        ]

    # topic_ids uids 至少有一个
    if not topic_ids and not uids:
        print("wxpusher 服务的 WXPUSHER_TOPIC_IDS 和 WXPUSHER_UIDS 至少设置一个!!")
        return

    print("wxpusher 服务启动")

    data = {
        "appToken": push_config.get("WXPUSHER_APP_TOKEN"),
        "content": f"<h1>{title}</h1><br/><div style='white-space: pre-wrap;'>{content}</div>",
        "summary": title,
        "contentType": 2,
        "topicIds": topic_ids,
        "uids": uids,
        "verifyPayType": 0,
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(url=url, json=data, headers=headers, timeout=15).json()

    if response.get("code") == 1000:
        print("wxpusher 推送成功！")
    else:
        print(f"wxpusher 推送失败！错误信息：{response.get('msg')}")


def parse_headers(headers):
    if not headers:
        return {}

    parsed = {}
    lines = headers.split("\n")

    for line in lines:
        i = line.find(":")
        if i == -1:
            continue

        key = line[:i].strip().lower()
        val = line[i + 1 :].strip()
        parsed[key] = parsed.get(key, "") + ", " + val if key in parsed else val

    return parsed


def parse_string(input_string, value_format_fn=None):
    matches = {}
    pattern = r"(\w+):\s*((?:(?!\n\w+:).)*)"
    # 深查第 16 轮：补 re.DOTALL（双生文件同改）。值模板里的 (?!\n\w+:) 本意是
    # “换行后不是下一个 key: 才继续吃”，但没 DOTALL 时 . 匹配不到 \n，
    # 展望恒为摆设，多行值在第一个换行处截断（如 content 写两行只剩首行）。
    # 补 DOTALL 后展望生效，多行值完整保留、到下一个 key: 才停；单行与
    # JSON 值行为不变（group(2) 仍 strip，json.loads 仍先试）。
    regex = re.compile(pattern, re.DOTALL)
    for match in regex.finditer(input_string):
        key, value = match.group(1).strip(), match.group(2).strip()
        try:
            value = value_format_fn(value) if value_format_fn else value
            json_value = json.loads(value)
            matches[key] = json_value
        except:
            matches[key] = value
    return matches


def parse_body(body, content_type, value_format_fn=None):
    if not body or content_type == "text/plain":
        return value_format_fn(body) if value_format_fn and body else body

    parsed = parse_string(body, value_format_fn)

    if content_type == "application/x-www-form-urlencoded":
        data = urllib.parse.urlencode(parsed, doseq=True)
        return data

    if content_type == "application/json":
        data = json.dumps(parsed)
        return data

    return parsed


def custom_notify(title: str, content: str) -> None:
    """
    通过 自定义通知 推送消息。
    """
    if not push_config.get("WEBHOOK_URL") or not push_config.get("WEBHOOK_METHOD"):
        return

    print("自定义通知服务启动")

    WEBHOOK_URL = push_config.get("WEBHOOK_URL")
    WEBHOOK_METHOD = push_config.get("WEBHOOK_METHOD")
    WEBHOOK_CONTENT_TYPE = push_config.get("WEBHOOK_CONTENT_TYPE")
    WEBHOOK_BODY = push_config.get("WEBHOOK_BODY")
    WEBHOOK_HEADERS = push_config.get("WEBHOOK_HEADERS")

    # 深查第 16 轮：请求头占位符（双生文件同改）。门禁文案写“请求头或者请求体
    # 中必须包含 $title”，但只查 URL/BODY 两处：$title 只放请求头时被误拦；
    # 且 parse_headers 出来的值从不替换，$title/$content 原样发出，
    # 上游收到字面量。门禁补查 WEBHOOK_HEADERS，头值按与 body 相同的
    # 转义（\n→\\n，头值禁裸换行）做替换；URL/BODY 逻辑不动。
    if (
        "$title" not in WEBHOOK_URL
        and "$title" not in WEBHOOK_BODY
        and "$title" not in (WEBHOOK_HEADERS or "")
    ):
        print("请求头或者请求体中必须包含 $title 和 $content")
        return

    headers = parse_headers(WEBHOOK_HEADERS)
    headers = {
        k: v.replace("$title", title.replace("\n", "\\n")).replace(
            "$content", content.replace("\n", "\\n")
        )
        for k, v in headers.items()
    }
    body = parse_body(
        WEBHOOK_BODY,
        WEBHOOK_CONTENT_TYPE,
        lambda v: v.replace("$title", title.replace("\n", "\\n")).replace(
            "$content", content.replace("\n", "\\n")
        ),
    )
    formatted_url = WEBHOOK_URL.replace(
        "$title", urllib.parse.quote_plus(title)
    ).replace("$content", urllib.parse.quote_plus(content))
    response = requests.request(
        method=WEBHOOK_METHOD, url=formatted_url, headers=headers, timeout=15, data=body
    )

    if response.status_code == 200:
        print("自定义通知推送成功！")
    else:
        print(f"自定义通知推送失败！{response.status_code} {response.text}")


def one() -> str:
    """
    获取一条一言。
    :return:
    """
    url = "https://v1.hitokoto.cn/"
    # 深查第 4 轮：一言只是装饰性附言，send() 却在主线程同步调用它，
    # 且原先无 timeout、无任何异常防护——上游挂起/断网/回非 JSON/缺字段时
    # 异常直接抛出，send() 在建通道线程之前就崩掉，全部通道一条都发不出去。
    # 改为 5 秒 fail-fast 超时（装饰接口不等同于推送通道，不沿用 15 秒），
    # 失败返回空串、只记日志，推送继续走；成功语义不变。
    try:
        res = requests.get(url, timeout=5).json()
        return res["hitokoto"] + "    ----" + res["from"]
    except Exception as e:
        print(f"一言获取失败，跳过一言继续推送！{e}")
        return ""


def add_notify_function():
    notify_function = []
    if push_config.get("BARK_PUSH"):
        notify_function.append(bark)
    # 深查第 14 轮：CONSOLE="false" 仍启用控制台输出（双生文件同改）。
    # 环境变量进来的都是字符串，"false" 非空即真值，原先直接判真值，
    # 用户写 CONSOLE=false 想关掉反而一直开着。同文件 HITOKOTO 已用
    # `!= "false"` 判定，CONSOLE 沿用同一约定（True/"true" 启用，
    # False/"false" 关闭），不改其他通道判定。
    # 深查第 20 轮：CONSOLE="False" 仍启用（双生文件同改）。第 14 轮只修了
    # 小写 "false"：字符串 "False"/"FALSE" 是真值且 != "false"，注释里写的
    # “False/\"false\" 关闭”对它们不成立。改大小写不敏感比较，与第 18/19
    # 轮 SMTP_SSL/HITOKOTO 同一做法；布尔 False 靠前半真值判定已关闭。
    if push_config.get("CONSOLE") and str(push_config.get("CONSOLE")).lower() != "false":
        notify_function.append(console)
    if push_config.get("DD_BOT_TOKEN") and push_config.get("DD_BOT_SECRET"):
        notify_function.append(dingding_bot)
    if push_config.get("FSKEY"):
        notify_function.append(feishu_bot)
    if push_config.get("GOBOT_URL") and push_config.get("GOBOT_QQ"):
        notify_function.append(go_cqhttp)
    if push_config.get("GOTIFY_URL") and push_config.get("GOTIFY_TOKEN"):
        notify_function.append(gotify)
    if push_config.get("IGOT_PUSH_KEY"):
        notify_function.append(iGot)
    if push_config.get("PUSH_KEY"):
        notify_function.append(serverJ)
    if push_config.get("DEER_KEY"):
        notify_function.append(pushdeer)
    if push_config.get("CHAT_URL") and push_config.get("CHAT_TOKEN"):
        notify_function.append(chat)
    if push_config.get("PUSH_PLUS_TOKEN"):
        notify_function.append(pushplus_bot)
    if push_config.get("WE_PLUS_BOT_TOKEN"):
        notify_function.append(weplus_bot)
    if push_config.get("QMSG_KEY") and push_config.get("QMSG_TYPE"):
        notify_function.append(qmsg_bot)
    if push_config.get("QYWX_AM"):
        notify_function.append(wecom_app)
    if push_config.get("QYWX_KEY"):
        notify_function.append(wecom_bot)
    if push_config.get("TG_BOT_TOKEN") and push_config.get("TG_USER_ID"):
        notify_function.append(telegram_bot)
    if (
        push_config.get("AIBOTK_KEY")
        and push_config.get("AIBOTK_TYPE")
        and push_config.get("AIBOTK_NAME")
    ):
        notify_function.append(aibotk)
    if (
        push_config.get("SMTP_SERVER")
        and push_config.get("SMTP_SSL")
        and push_config.get("SMTP_EMAIL")
        and push_config.get("SMTP_PASSWORD")
        and push_config.get("SMTP_NAME")
    ):
        notify_function.append(smtp)
    if push_config.get("PUSHME_KEY"):
        notify_function.append(pushme)
    if (
        push_config.get("CHRONOCAT_URL")
        and push_config.get("CHRONOCAT_QQ")
        and push_config.get("CHRONOCAT_TOKEN")
    ):
        notify_function.append(chronocat)
    if push_config.get("WEBHOOK_URL") and push_config.get("WEBHOOK_METHOD"):
        notify_function.append(custom_notify)
    if push_config.get("NTFY_TOPIC"):
        notify_function.append(ntfy)
    if push_config.get("WXPUSHER_APP_TOKEN") and (
        push_config.get("WXPUSHER_TOPIC_IDS") or push_config.get("WXPUSHER_UIDS")
    ):
        notify_function.append(wxpusher_bot)
    if not notify_function:
        print(f"无推送渠道，请检查通知变量是否正确")
    return notify_function


# 深查第 5 轮：send() 的总耗时上限（单点收敛，详见 REPORT.md）。
# 线程并行跑各通道，但原先的 `[t.join() for t in ts]` 无 timeout：18 处
# requests 调用（含 feishu/gotify/iGot/serverJ/pushdeer 等）与 SMTP 均无
# timeout，任一通道上游挂起，send() 就永远不返回——CONSOLE 等已完成
# 的通道也等不到返回，调用方脚本随之卡死。逐通道补 timeout 是 18 处，
# 本轮只在唯一的汇合点 send() 收敛：总预算 60 秒（墙钟，按最慢的单
# 个通道计，不是各通道求和；60 = 4 × 单请求 15 秒，容得下 WeCom 取
# token 再发消息、chronocat 循环发多条等单线程多请求形态）。
# 注意 join(timeout) 只放行 send() 返回，不杀死线程：超时线程若进程
# 未退出仍可能随后完成推送；daemon=True 是为进程退出时不再被挂起
# 线程拖住（默认非 daemon 线程会让解释器退出时一直等）。
SEND_JOIN_TIMEOUT = 60  # 秒，send() 等全部通道的最长墙钟时间


# 深查第 9 轮：通道异常收敛到 send() 的唯一线程入口（双生文件同改）。
# 各通道仍可能抛错：第 7 轮补 timeout 后超时以 requests 超时异常抛出、
# 上游回 HTML 错误页时 .json() 抛 ValueError、wxpusher 的 int(topic_id)
# 遇非数字抛 ValueError——原先直接以 target=mode 起线程，异常只剩
# threading 往 stderr 打的 traceback，没有"某通道推送失败"这一行，
# 且与第 5 轮的超时点名格式不一致。改为统一包一层：单通道异常只记一行、
# 不杀死其余通道线程、不影响 send() 返回；线程名仍用通道函数名，
# 第 5 轮的"仍未完成通道"点名不受影响。
def _run_channel(mode, title, content):
    try:
        mode(title, content)
    except Exception as e:
        print(f"{mode.__name__} 推送异常：{e}，该通道跳过，继续执行其余通道！")


def send(title: str, content: str, ignore_default_config: bool = False, **kwargs):
    if kwargs:
        global push_config
        if ignore_default_config:
            push_config = kwargs  # 清空从环境变量获取的配置
        else:
            push_config.update(kwargs)

    if not content:
        print(f"{title} 推送内容为空！")
        return

    # 根据标题跳过一些消息推送，环境变量：SKIP_PUSH_TITLE 用回车分隔
    skipTitle = os.getenv("SKIP_PUSH_TITLE")
    if skipTitle:
        # 深查第 21 轮：按 \r?\n 分隔并 strip 条目（双生文件同改）。环境变量从
        # Windows 粘贴常带 \r\n：re.split("\n") 切出 "日报\r"，标题 "日报"
        # 永远匹配不上，该跳过的照发不误；条目首尾空格同理。strip 后比对，
        # 空条目过滤；标题本身不 strip（标题是调用方原样传入的）。
        if title in [t.strip() for t in re.split(r"\r?\n", skipTitle) if t.strip()]:
            print(f"{title} 在SKIP_PUSH_TITLE环境变量内，跳过推送！")
            return

    # 深查第 19 轮：HITOKOTO 布尔 False 仍调一言（双生文件同改）。与第 14 轮
    # CONSOLE、第 18 轮 SMTP_SSL 同类：字符串布尔判定。`!= "false"` 只认
    # 小写字符串，经 kwargs 传布尔 False 时仍为真值，one() 照调不误——
    # 用户明明关了一言，send() 每次仍多一次上游请求（失败只记日志不致命，
    # 但违背配置）。改大小写不敏感比较，str() 包一层兼顾布尔。
    hitokoto = push_config.get("HITOKOTO")
    content += "\n\n" + one() if str(hitokoto).lower() != "false" else ""

    notify_function = add_notify_function()
    ts = [
        threading.Thread(
            target=_run_channel,
            args=(mode, title, content),
            name=mode.__name__,
            daemon=True,
        )
        for mode in notify_function
    ]
    [t.start() for t in ts]
    # 总预算按统一 deadline 扣：逐个 join 剩余时间，避免每线程 60 秒叠加成 N×60。
    deadline = time.monotonic() + SEND_JOIN_TIMEOUT
    for t in ts:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        t.join(timeout=remaining)
    unfinished = [t.name for t in ts if t.is_alive()]
    if unfinished:
        print(f"推送超时，仍未完成的通道：{', '.join(unfinished)}，已跳过等待继续执行！")


def main():
    send("title", "content")


if __name__ == "__main__":
    main()
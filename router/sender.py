"""总结/原文发送到外部 agent 的发送层（可插拔 sink）。

两类目的地：
- mcp：通过 MCP（Model Context Protocol，让不同 AI agent 互相打通、互相调用的协议/标准）
       调用目标 agent 暴露的工具（tool），把摘要作为参数传过去。
- connector：通过用户自定义的 HTTP webhook（连接器）把摘要 POST 出去。
   任何支持接收 HTTP POST 的服务都能接（自建服务、Zapier/Make、飞书/企业微信机器人、
   n8n、WorkBuddy 自定义连接器、其它 agent 的接收接口等）。
   连接信息从 web/local_config.json 的 connector 段读取。

未配置时给出清晰报错，而不是静默失败。
"""

import json
import os
import time
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
# router/ 的上一级是 Character/，再进 web/ 才是 local_config.json
_LOCAL_CONFIG = os.path.join(os.path.dirname(_HERE), "web", "local_config.json")


def _load_config():
    try:
        with open(_LOCAL_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def send_to_mcp(text, target=None):
    """把 text 通过 MCP 发给目标 agent 的工具。

    待接入：需要你在 local_config.json 的 mcp 段填写：
      - server：MCP server 的连接方式（stdio 启动命令，或 SSE/HTTP 地址）
      - tool：接收摘要的工具名
      - 以及该工具的参数格式（字段名）
    确认后我会在这里补上真正的 MCP 客户端调用（连接 server → 调用 tool）。
    """
    cfg = _load_config().get("mcp", {})
    if not cfg.get("server") or not cfg.get("tool"):
        raise RuntimeError(
            "MCP 未配置：请在 local_config.json 的 mcp 段填写 server（连接方式）与 tool（工具名）"
        )
    # TODO: 真正的 MCP 客户端调用（连接 server → 调用 tool，把 text 作为参数传过去）。
    raise NotImplementedError("MCP 发送尚未接入：已读到配置，但客户端调用待实现（需要你确认连接方式）")


def send_to_connector(text, target=None):
    """把 text 通过用户自定义的 HTTP webhook（连接器）POST 出去。

    local_config.json 的 connector 段支持：
      - endpoint：     接收地址（必填）
      - method：       默认 POST
      - auth_token：   若填写，会加 Authorization: Bearer <token>
      - payload_field：摘要放入的字段名；留空则整个 body 为
                       {"text": ..., "source": "Character", "timestamp": ...}
      - extra：        额外固定字段（dict），随摘要一起发送
      - headers：      额外自定义请求头（dict），与上面的 Authorization 合并
      - timeout：      请求超时秒数，默认 30

    返回一段简短的成功描述。失败抛 RuntimeError（含 HTTP 状态码 / 原因）。
    """
    cfg = _load_config().get("connector", {})
    endpoint = (cfg.get("endpoint") or "").strip()
    if not endpoint:
        raise RuntimeError(
            "连接器未配置：请在 local_config.json 的 connector 段填写 endpoint（webhook 接收地址）"
        )

    method = (cfg.get("method") or "POST").upper()
    field = (cfg.get("payload_field") or "").strip()
    extra = cfg.get("extra") or {}
    if not isinstance(extra, dict):
        extra = {}

    if field:
        payload = {field: text}
    else:
        payload = {
            "text": text,
            "source": "Character",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    payload.update(extra)

    headers = {"Content-Type": "application/json"}
    token = (cfg.get("auth_token") or "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    for k, v in (cfg.get("headers") or {}).items():
        headers[str(k)] = str(v)

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    timeout = int(cfg.get("timeout") or 30)
    req = urllib.request.Request(endpoint, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            return "已发送到连接器 %s（HTTP %s）" % (endpoint, code)
    except urllib.error.HTTPError as e:
        raise RuntimeError("连接器返回错误：HTTP %s —— %s" % (e.code, endpoint))
    except Exception as e:
        raise RuntimeError("连接器请求失败：%s —— %s" % (e, endpoint))

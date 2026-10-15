#!/usr/bin/env python3
"""本地调试 playground：网页入口 + /api/process 管线。

零第三方依赖（只用标准库 http.server）。启动：python3 web/server.py
默认端口 8787，浏览器开 http://localhost:8787

用途：拿你自己的 JEV key + OpenAI key，在网页里贴内容、调阈值/接口地址，
实时看 JEV 分类、是否需要 LLM、总结结果和生成的 md。纯调试工具，不是消费端。
"""

import json
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)  # 让根目录 router/ 能被直接 import

from router.route import route, needs_summary
from router.summarizer import summarize
from router.extractor import extract_fields
from router.md_writer import generate_md, save_md, save_raw_md, generate_raw_md

PORT = int(os.environ.get("PORT", "8787"))
OUT = os.path.join(ROOT, "outputs")
LOCAL_CONFIG = os.path.join(HERE, "local_config.json")   # 本机 key 配置（不进版本库）


def _local_config():
    """读本机配置：把 key 放这里，网页设置面板留空也能跑真实模型。"""
    try:
        with open(LOCAL_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def default_jev_key():
    """默认 JEV key：环境变量优先，其次本机配置文件。"""
    return os.environ.get("TYPESAFE_API_KEY") or _local_config().get("jev_key") or ""


def default_llm_key():
    """默认 LLM key：环境变量优先，其次本机配置文件。"""
    return os.environ.get("LLM_API_KEY") or _local_config().get("openai_key") or ""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json", cache=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/config":
            # 前端用它判断当前是真实模型还是 mock（决定比例要不要按真 key 重算），
            # 并把本机配置的 key 同步进设置面板（只监听 127.0.0.1，不对外）
            self._send(200, {
                "jev": "real" if default_jev_key() else "mock",
                "llm": "real" if default_llm_key() else "none",
                "jev_key": default_jev_key(),
                "openai_key": default_llm_key(),
            })
        elif path in ("/", "/index.html"):
            self._serve_file("index.html")
        elif path in ("/app", "/app.html"):
            self._serve_file("app.html")
        else:
            # 静态资源：放行 web 目录下的普通文件（含子目录，如 vendor/pretext/*.js），禁止路径穿越
            rel = path.lstrip("/")
            full = os.path.normpath(os.path.join(HERE, rel))
            safe = (
                rel
                and full.startswith(HERE + os.sep)
                and os.path.isfile(full)
                and not any(seg.startswith(".") for seg in rel.split("/"))
            )
            if safe:
                self._serve_path(full)
            else:
                self._send(404, {"error": "not found"})

    def _ctype_for(self, name):
        if name.endswith(".css"):
            return "text/css"
        if name.endswith(".js"):
            return "application/javascript"
        if name.endswith(".json"):
            return "application/json"
        if name.endswith(".woff2"):
            return "font/woff2"
        if name.endswith(".svg"):
            return "image/svg+xml"
        return "text/html"

    def _cache_for(self, name):
        """字体文件永不改，长缓存；会不断迭代的 html/css/js 一律 no-store。
        不设这个头的话浏览器会启发式缓存，改了代码却看到旧页面，排查起来极费劲。"""
        if name.endswith((".woff2", ".woff", ".ttf", ".otf")):
            return "public, max-age=31536000, immutable"
        return "no-store, must-revalidate"

    def _serve_path(self, full):
        # 统一二进制读取：文本照常工作，字体等二进制文件不再解码崩溃
        with open(full, "rb") as f:
            self._send(200, f.read(), self._ctype_for(full), self._cache_for(full))

    def _serve_file(self, name):
        self._serve_path(os.path.join(HERE, name))

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/classify":
            self._classify()          # 只分类、不落盘（历史记录回填「归类比例」用）
            return
        if path == "/api/summarize":
            self._summarize()         # 总结按钮：强制走 LLM 出摘要（不存档）
            return
        if path == "/api/send":
            self._send_to_agent()     # 总结后把摘要发到外部 agent（MCP / 自定义连接器）
            return
        if path != "/api/process":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            req = json.loads(raw.decode("utf-8"))
        except Exception as e:
            self._send(400, {"error": f"bad request: {e}"})
            return

        text = (req.get("text") or "").strip()
        if not text:
            self._send(400, {"error": "text 不能为空"})
            return

        mode = (req.get("mode") or "full").lower()          # "full" | "archive_only"
        project = (req.get("project") or "").strip()
        jev_key = req.get("jev_key") or default_jev_key()      # 网页没填就用本机配置的 key
        # GLM 密钥以本机配置文件(local_config.json)为准：避免浏览器里存了旧 key 把新 key 盖掉
        openai_key = default_llm_key() or req.get("openai_key")
        # 默认指向 GLM（智谱），没传接口地址/模型时用，避免回落到 OpenAI 默认地址
        llm_base = req.get("llm_base") or "https://open.bigmodel.cn/api/paas/v4"
        llm_model = req.get("llm_model") or "glm-4-flash"
        try:
            threshold = float(req.get("threshold", 0.7))
        except ValueError:
            threshold = 0.7

        use_jev_mock = not bool(jev_key)
        use_llm_mock = not bool(openai_key)
        ts = datetime.now().strftime("%H%M%S")
        title = text.split("\n", 1)[0][:40]
        raw_path = None

        try:
            # ① 先存档：把原始内容落盘成纯原文 md（不依赖 JEV/LLM，先保记录）
            raw_path = save_raw_md(text, out_dir=OUT, project=project, ts=ts)

            if mode == "archive_only":
                # 创造模式：只记录、不处理
                self._send(200, {
                    "mode": "archive_only",
                    "title": title,
                    "raw_md_path": raw_path,
                    "raw_md": generate_raw_md(text, project=project),
                })
                return

            # ② 后处理：JEV 路由 + OpenAI 总结
            r = route(text, api_key=jev_key or None, use_mock=use_jev_mock,
                      need_llm_threshold=threshold)
            summary = None
            extra_fields = None
            if needs_summary(r):
                summary = summarize(text, r["final_skill"],
                                    api_key=openai_key or None,
                                    base_url=llm_base, model=llm_model,
                                    use_mock=use_llm_mock)
            else:
                extra_fields = extract_fields(text, api_key=jev_key or None,
                                             use_mock=use_jev_mock)
            summary_path = save_md(text, r, out_dir=OUT, idx=ts,
                                   summary=summary, extra_fields=extra_fields,
                                   project=project)
            self._send(200, {
                "route": r,
                "summary": summary,
                "extra_fields": extra_fields,
                "md": generate_md(text, r, summary=summary,
                                  extra_fields=extra_fields, project=project),
                "raw_md_path": raw_path,
                "summary_md_path": summary_path,
                "raw_md": generate_raw_md(text, project=project),
                "title": title,
                "mode": {
                    "jev": "mock" if use_jev_mock else "real",
                    "llm": "mock" if use_llm_mock else "real",
                },
            })
        except Exception as e:
            # 存档已落盘：返回 raw 路径 + 错误，保证原始记录不丢
            self._send(500, {"error": str(e), "type": type(e).__name__,
                             "raw_md_path": raw_path})

    def _classify(self):
        """只跑 JEV 分类、不写任何文件：给历史记录回填「归类比例」用。"""
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception as e:
            self._send(400, {"error": f"bad request: {e}"})
            return

        text = (req.get("text") or "").strip()
        if not text:
            self._send(400, {"error": "text 不能为空"})
            return

        jev_key = req.get("jev_key") or default_jev_key()
        try:
            threshold = float(req.get("threshold", 0.7))
        except ValueError:
            threshold = 0.7
        try:
            r = route(text, api_key=jev_key or None, use_mock=not bool(jev_key),
                      need_llm_threshold=threshold)
            self._send(200, {"route": r,
                             "mode": {"jev": "mock" if not jev_key else "real"}})
        except Exception as e:
            self._send(500, {"error": str(e), "type": type(e).__name__})

    def _summarize(self):
        """总结按钮：把输入路由到类别，再按情况出总结（不存档、不落盘）。

        - 配了 LLM key：真调大模型出摘要；
        - 没配任何模型：不调 LLM、不出假摘要，原样打包（packaged=true），
          由前端标注「未连接模型」，用户一键复制后交给 Agent 处理；
        - 灵感类(inspiration)不重写，summary 为 None。

        返回 {summary, skill, packaged, mode}。
        """
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception as e:
            self._send(400, {"error": f"bad request: {e}"})
            return

        text = (req.get("text") or "").strip()
        if not text:
            self._send(400, {"error": "text 不能为空"})
            return

        jev_key = req.get("jev_key") or default_jev_key()
        # GLM 密钥以本机配置文件(local_config.json)为准：避免浏览器里存了旧 key 把新 key 盖掉
        openai_key = default_llm_key() or req.get("openai_key")
        print("[debug] summarize 实际使用的 openai_key 前缀:", (openai_key or "")[:8], file=sys.stderr)
        # 默认指向 GLM（智谱），没传接口地址/模型时用，避免回落到 OpenAI 默认地址
        llm_base = req.get("llm_base") or "https://open.bigmodel.cn/api/paas/v4"
        llm_model = req.get("llm_model") or "glm-4-flash"
        try:
            summary = None
            packaged = False
            skill = None
            if jev_key:
                # JEV 已连：先分类；灵感类按设计不重写
                try:
                    r = route(text, api_key=jev_key, use_mock=False)
                    skill = r["final_skill"]
                except Exception:
                    skill = None
            # 没连 JEV：不分类、不走「灵感类不重写」规则，直接交给 GLM 总结（若有 key）
            if openai_key and skill != "inspiration":
                summary = summarize(text, skill, api_key=openai_key, base_url=llm_base, model=llm_model, use_mock=False)
            elif not openai_key:
                packaged = True   # 没连任何模型：原样打包，不产假摘要

            self._send(200, {
                "summary": summary,
                "skill": skill,
                "packaged": packaged,
                "mode": {"jev": "mock" if not jev_key else "real",
                         "llm": "real" if openai_key else "none"},
            })
            return
        except Exception as e:
            self._send(500, {"error": str(e), "type": type(e).__name__})

    def _send_to_agent(self):
        """把摘要/原文发到外部 agent（MCP 或自定义连接器），具体逻辑在 router/sender.py。

        未配置目标时返回 ok:false + 清晰报错，而不是 500。
        """
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception as e:
            self._send(400, {"error": f"bad request: {e}"})
            return

        dest = (req.get("destination") or "").lower()
        text = (req.get("text") or "").strip()
        if not text:
            self._send(400, {"error": "text 不能为空"})
            return
        try:
            from router.sender import send_to_mcp, send_to_connector
            if dest == "mcp":
                detail = send_to_mcp(text, req.get("target"))
            elif dest == "connector":
                detail = send_to_connector(text, req.get("target"))
            else:
                self._send(400, {"error": f"未知目的地：{dest}"})
                return
            self._send(200, {"ok": True, "destination": dest, "detail": str(detail)})
        except Exception as e:
            self._send(200, {"ok": False, "destination": dest, "error": str(e)})

    def log_message(self, *args):
        pass  # 安静点


if __name__ == "__main__":
    print(f"playground 启动： http://localhost:{PORT}  (Ctrl+C 退出)")
    print("JEV key：" + ("已配置（网页设置留空即用）" if default_jev_key() else "未配置 → 分类走 mock"))
    print("LLM key：" + ("已配置" if default_llm_key() else "未配置 → 总结走 mock"))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

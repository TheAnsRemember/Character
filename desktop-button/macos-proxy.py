#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character 本地域名转发器（纯标准库，零依赖）。

把本机 80 端口（character.test 域名）上的请求，原样转发到 127.0.0.1:8787
的 Character 服务。作为 launchd 守护进程运行：开机自启、崩溃自动重启。

设计要点
--------
- 纯 TCP 字节转发，不解析 HTTP，因此 Host 头里写什么（character.test）都能
  原样透传给后端，后端 http.server 不挑主机名，正常响应。
- 只监听 127.0.0.1，不对外网暴露，安全边界清晰。
- 需要 root 才能绑定 80（特权端口），故由 /Library/LaunchDaemons 以 root 加载。

用法：
    python3 macos-proxy.py [LISTEN_PORT] [UPSTREAM_HOST:UPSTREAM_PORT]
默认监听 80 转发到 127.0.0.1:8787；LISTEN_PORT 也可用环境变量 LISTEN_PORT 覆盖。
"""
import os
import sys
import socket
import threading

DEFAULT_LISTEN = int(os.environ.get("LISTEN_PORT", "80"))
DEFAULT_UPSTREAM_HOST = "127.0.0.1"
DEFAULT_UPSTREAM_PORT = 8787
BUFFER = 65536


def parse_upstream(spec):
    """把 'host:port' 解析成 (host, port)，解析失败回退默认。"""
    if not spec:
        return DEFAULT_UPSTREAM_HOST, DEFAULT_UPSTREAM_PORT
    host, sep, port = spec.rpartition(":")
    if not sep:
        return DEFAULT_UPSTREAM_HOST, DEFAULT_UPSTREAM_PORT
    try:
        return (host or DEFAULT_UPSTREAM_HOST, int(port))
    except ValueError:
        return DEFAULT_UPSTREAM_HOST, DEFAULT_UPSTREAM_PORT


def _close(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


def forward(src, dst):
    """把 src 收到的字节源源不断写到 dst，任一侧关闭即结束。"""
    try:
        while True:
            data = src.recv(BUFFER)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        _close(src)
        _close(dst)


def handle(client, upstream):
    """为每个入站连接开一条到后端的连接，双向搬运。"""
    try:
        up = socket.create_connection(upstream, timeout=10)
    except OSError as exc:
        sys.stderr.write("upstream connect failed: %s\n" % exc)
        sys.stderr.flush()
        _close(client)
        return
    t1 = threading.Thread(target=forward, args=(client, up), daemon=True)
    t2 = threading.Thread(target=forward, args=(up, client), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()


def main():
    listen = DEFAULT_LISTEN
    if len(sys.argv) > 1:
        try:
            listen = int(sys.argv[1])
        except ValueError:
            pass
    upstream = parse_upstream(sys.argv[2] if len(sys.argv) > 2 else "")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", listen))   # 仅本机回路，不暴露到局域网
    srv.listen(128)
    sys.stdout.write("Character proxy :%d -> %s:%d  (pid %d)\n"
                     % (listen, upstream[0], upstream[1], os.getpid()))
    sys.stdout.flush()

    while True:
        try:
            client, _addr = srv.accept()
        except OSError:
            break
        threading.Thread(target=handle, args=(client, upstream), daemon=True).start()


if __name__ == "__main__":
    main()

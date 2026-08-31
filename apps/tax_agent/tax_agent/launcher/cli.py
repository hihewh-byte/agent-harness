"""tax-agent — stable user-facing CLI (replaces ad-hoc scripts)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tax_agent.launcher.daemon import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    open_browser,
    start,
    status,
    stop,
)
from tax_agent.launcher.manifest import LAUNCHER_MANIFEST

ROOT = Path(__file__).resolve().parent.parent.parent


def _cmd_start(args: argparse.Namespace) -> int:
    st = start(args.host, args.port, wait_ready=not args.no_wait)
    print(json.dumps(st, ensure_ascii=False, indent=2))
    return 0 if st.get("healthy") else 1


def _cmd_stop(_: argparse.Namespace) -> int:
    st = stop()
    print(json.dumps(st, ensure_ascii=False, indent=2))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    st = status(args.host, args.port)
    print(json.dumps(st, ensure_ascii=False, indent=2))
    return 0 if st.get("healthy") else 1


def _cmd_open(args: argparse.Namespace) -> int:
    if not status(args.host, args.port).get("healthy"):
        print("服务未运行，正在启动…", file=sys.stderr)
        st = start(args.host, args.port)
        if not st.get("healthy"):
            print("启动失败，见 .data/tax_agent.log", file=sys.stderr)
            return 1
    open_browser(args.path, args.host, args.port)
    print(f"已打开 http://{args.host}:{args.port}{args.path}")
    return 0


def _cmd_app(args: argparse.Namespace) -> int:
    """One-shot: start server + open control app."""
    return _cmd_open(args)


def _cmd_selfcheck(_: argparse.Namespace) -> int:
    script = ROOT / "scripts" / "run_all_selfchecks.py"
    if not script.is_file():
        print(f"missing {script}", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, str(script)], cwd=str(ROOT))


def _cmd_manifest(_: argparse.Namespace) -> int:
    print(json.dumps(LAUNCHER_MANIFEST, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tax-agent",
        description="Tax Agent 稳定启动器（与计税引擎解耦，通过 HTTP API 使用）",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="后台启动 API 服务")
    p_start.add_argument("--no-wait", action="store_true", help="不等待 /health 就绪")
    p_start.set_defaults(func=_cmd_start)

    p_stop = sub.add_parser("stop", help="停止服务")
    p_stop.set_defaults(func=_cmd_stop)

    sub.add_parser("status", help="服务状态").set_defaults(func=_cmd_status)

    p_open = sub.add_parser("open", help="打开浏览器")
    p_open.add_argument(
        "--path",
        default="/app",
        help="路径，默认 /app 控制台；报税助手用 /",
    )
    p_open.set_defaults(func=_cmd_open)

    p_app = sub.add_parser("app", help="启动服务并打开控制台（推荐）")
    p_app.add_argument("--path", default="/app")
    p_app.set_defaults(func=_cmd_app)

    sub.add_parser("selfcheck", help="运行全量自检（原 run_all_selfchecks.py）").set_defaults(
        func=_cmd_selfcheck
    )

    sub.add_parser("manifest", help="打印稳定 API/页面契约").set_defaults(func=_cmd_manifest)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

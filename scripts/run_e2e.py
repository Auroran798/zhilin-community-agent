"""Run isolated API checks and real browser business journeys.

The report distinguishes HTTP integration checks from actions performed in the
Streamlit UI. A login-only screenshot is never counted as a business E2E pass.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/e2e"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_port(port: int, process: subprocess.Popen[bytes], seconds: int = 45) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"process exited with {process.returncode}")
        with socket.socket() as probe:
            probe.settimeout(0.3)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.25)
    raise TimeoutError(f"port {port} did not become ready")


def browser_executable() -> str | None:
    configured = os.environ.get("CHROME_EXECUTABLE")
    candidates = ([Path(configured)] if configured else []) + [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    return next((str(path) for path in candidates if path.exists()), None)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / "tmp" / f"e2e-{uuid.uuid4().hex}"
    runtime.mkdir(parents=True)
    api_port, web_port = free_port(), free_port()
    env = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{(runtime / 'e2e.db').as_posix()}",
        "RAG_STORAGE_PATH": str(runtime / "knowledge"),
        "RAG_CHROMA_PATH": str(runtime / "chroma"),
        "AGENT_CHECKPOINT_PATH": str(runtime / "agent.sqlite"),
        "API_BASE_URL": f"http://127.0.0.1:{api_port}",
    }
    api = web = None
    api_log_path, web_log_path = OUT / "e2e_api.log", OUT / "e2e_web.log"
    api_log = api_log_path.open("wb")
    web_log = web_log_path.open("wb")
    report: dict = {
        "status": "FAIL",
        "isolation": "temporary database, files, vector store and checkpoint",
        "scenarios": [],
        "artifacts": [],
    }
    try:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True)
        subprocess.run([sys.executable, "-m", "data.seed"], cwd=ROOT, env=env, check=True)
        api = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(api_port)],
            cwd=ROOT, env=env, stdout=api_log, stderr=subprocess.STDOUT,
        )
        wait_port(api_port, api)
        web = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "web/app.py", "--server.address", "127.0.0.1", "--server.port", str(web_port), "--server.headless", "true"],
            cwd=ROOT, env=env, stdout=web_log, stderr=subprocess.STDOUT,
        )
        wait_port(web_port, web)
        api_url = f"http://127.0.0.1:{api_port}"

        def login_api(username: str) -> tuple[dict[str, str], dict]:
            response = requests.post(
                f"{api_url}/api/v1/auth/login",
                json={"username": username, "password": "DemoPass123!"}, timeout=10,
            )
            response.raise_for_status()
            payload = response.json()["data"]
            return {"Authorization": f"Bearer {payload['access_token']}"}, payload["user"]

        def call(auth: dict[str, str], method: str, path: str, expected: int = 200, **kwargs):
            extra = kwargs.pop("headers", {})
            response = requests.request(
                method, f"{api_url}{path}", headers={**auth, **extra}, timeout=15, **kwargs,
            )
            if response.status_code != expected:
                raise AssertionError(f"{method} {path}: {response.status_code}: {response.text}")
            return response.json().get("data")

        def poll(auth: dict[str, str], path: str, predicate, seconds: int = 12):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                value = call(auth, "GET", path)
                if predicate(value):
                    return value
                time.sleep(0.35)
            raise AssertionError(f"timed out waiting for {path}")

        resident, _ = login_api("resident_demo")
        service, _ = login_api("service_demo")
        maintenance, maintenance_user = login_api("maintenance_demo")
        manager, _ = login_api("manager_demo")
        report["scenarios"].append({"name": "four roles authenticate", "evidence_type": "api_integration", "status": "PASS"})

        property_id = call(resident, "GET", "/api/v1/properties/my")[0]["id"]
        foreign_bill = next(x for x in call(service, "GET", "/api/v1/bills") if x["property_id"] != property_id)
        forbidden = requests.get(f"{api_url}/api/v1/bills/{foreign_bill['id']}", headers=resident, timeout=10)
        assert forbidden.status_code == 403
        report["scenarios"].append({"name": "cross-property bill access is denied", "evidence_type": "api_integration", "status": "PASS"})

        idem_key = f"e2e-{uuid.uuid4()}"
        idem_payload = {
            "property_id": property_id, "original_description": "地下车库照明故障",
            "summary": "公共照明报修", "category": "公共照明",
            "location_description": "地下车库入口", "fault_description": "照明灯不亮",
        }
        first = call(resident, "POST", "/api/v1/work-orders", json=idem_payload, headers={"Idempotency-Key": idem_key})
        replay = call(resident, "POST", "/api/v1/work-orders", json=idem_payload, headers={"Idempotency-Key": idem_key})
        assert first["id"] == replay["id"]
        report["scenarios"].append({"name": "same scoped write is replayed once", "evidence_type": "api_integration", "status": "PASS"})

        executable = browser_executable()
        from playwright.sync_api import expect, sync_playwright

        def login_page(browser, username: str):
            context = browser.new_context(locale="zh-CN")
            page = context.new_page()
            page.goto(f"http://127.0.0.1:{web_port}", wait_until="networkidle")
            page.get_by_label("用户名").fill(username)
            page.get_by_label("密码").fill("DemoPass123!")
            page.get_by_role("button", name="登录", exact=True).click()
            expect(page.get_by_label("用户名")).to_have_count(0, timeout=15_000)
            expect(page.get_by_role("button", name="退出登录")).to_be_visible(timeout=15_000)
            page.wait_for_timeout(700)
            return context, page

        def switch_user(page, username: str) -> None:
            page.get_by_role("button", name="退出登录").click()
            expect(page.get_by_label("用户名")).to_be_visible(timeout=15_000)
            # Let the logout rerun settle before submitting the next form.
            page.wait_for_timeout(1200)
            page.get_by_label("用户名").fill(username)
            page.get_by_label("密码").fill("DemoPass123!")
            page.get_by_role("button", name="登录", exact=True).click()
            expect(page.get_by_label("用户名")).to_have_count(0, timeout=15_000)
            expect(page.get_by_role("button", name="退出登录")).to_be_visible(timeout=15_000)
            page.wait_for_timeout(700)

        def menu(page, name: str) -> None:
            # Target the radio control, not matching table/body text.
            target=page.locator("[data-testid='stSidebar'] label").filter(has_text=name)
            target.wait_for(state="visible",timeout=30_000)
            target.click()
            page.wait_for_timeout(700)

        def choose(page, label: str, value: str) -> None:
            box = page.get_by_role("combobox", name=label)
            box.click()
            # Streamlit virtualizes longer option lists, so off-screen values
            # may not exist as text nodes. Filter through the combobox input.
            box.fill(value)
            page.wait_for_timeout(250)
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)

        with sync_playwright() as playwright:
            launch = {"headless": True}
            if executable:
                launch["executable_path"] = executable
            browser = playwright.chromium.launch(**launch)

            resident_context, resident_page = login_page(browser, "resident_demo")
            resident_context.tracing.start(screenshots=True, snapshots=True, sources=True)
            menu(resident_page, "创建报修")
            resident_page.get_by_label("位置描述").fill("2号楼一层走廊")
            resident_page.get_by_label("故障描述").fill("走廊灯闪烁后熄灭")
            resident_page.get_by_role("button", name="提交报修").click()
            expect(resident_page.get_by_text("工单已创建", exact=True)).to_be_visible(timeout=12_000)
            ui_orders = call(resident, "GET", "/api/v1/work-orders")
            order = next(x for x in ui_orders if x["location_description"] == "2号楼一层走廊")
            order_id = order["id"]
            resident_page.screenshot(path=str(OUT / "resident_created_work_order.png"), full_page=True)
            report["scenarios"].append({"name": "resident creates a repair in UI", "evidence_type": "browser_business_flow", "status": "PASS"})

            switch_user(resident_page, "service_demo")
            service_page = resident_page
            menu(service_page, "工单管理")
            choose(service_page, "选择工单", order_id)
            service_page.get_by_role("button", name="受理选中工单").click()
            poll(service, f"/api/v1/work-orders/{order_id}", lambda value: value["status"] == "已受理")
            menu(service_page, "通知中心"); menu(service_page, "工单管理")
            choose(service_page, "选择工单", order_id)
            service_page.get_by_label("维修人员ID").fill(maintenance_user["id"])
            service_page.get_by_role("button", name="派单", exact=True).click()
            poll(service, f"/api/v1/work-orders/{order_id}", lambda value: value["status"] == "已派单")

            switch_user(service_page, "maintenance_demo")
            maintenance_page = service_page
            menu(maintenance_page, "我的工单")
            choose(maintenance_page, "选择工单", order_id)
            maintenance_page.get_by_role("button", name="开始处理").click()
            poll(maintenance, f"/api/v1/work-orders/{order_id}", lambda value: value["status"] == "处理中")
            menu(maintenance_page, "通知中心"); menu(maintenance_page, "我的工单")
            choose(maintenance_page, "选择工单", order_id)
            maintenance_page.get_by_label("处理结果").fill("更换灯具并复测正常")
            maintenance_page.get_by_role("button", name="提交居民确认").click()
            poll(maintenance, f"/api/v1/work-orders/{order_id}", lambda value: value["status"] == "待居民确认")

            switch_user(maintenance_page, "resident_demo")
            resident_page = maintenance_page
            menu(resident_page, "我的工单")
            choose(resident_page, "选择工单", order_id)
            resident_page.get_by_role("button", name="确认维修完成").click()
            poll(resident, f"/api/v1/work-orders/{order_id}", lambda value: value["status"] == "已完成")
            resident_page.screenshot(path=str(OUT / "work_order_completed.png"), full_page=True)
            report["scenarios"].append({"name": "service-maintenance-resident lifecycle in UI", "evidence_type": "browser_business_flow", "status": "PASS"})

            title = f"E2E 停水通知 {uuid.uuid4().hex[:6]}"
            switch_user(resident_page, "service_demo")
            service_page = resident_page
            menu(service_page, "公告草稿")
            service_page.get_by_label("标题").fill(title)
            service_page.get_by_label("内容").fill("因水泵检修，预计停水一小时。")
            service_page.get_by_label("影响范围").fill("Demo Garden")
            service_page.get_by_role("button", name="保存草稿").click()
            announcement = next(x for x in call(service, "GET", "/api/v1/announcements") if x["title"] == title)
            menu(service_page, "通知中心"); menu(service_page, "公告草稿")
            choose(service_page, "选择待提交草稿", title)
            service_page.get_by_role("button", name="提交人工审核").click()
            poll(service, "/api/v1/announcements", lambda values: any(x["id"] == announcement["id"] and x["status"] == "pending_review" for x in values))

            switch_user(service_page, "manager_demo")
            manager_page = service_page
            menu(manager_page, "公告审核发布")
            choose(manager_page, "公告", f"{title}（pending_review）")
            manager_page.get_by_role("button", name="审核通过").click()
            poll(manager, "/api/v1/announcements", lambda values: any(x["id"] == announcement["id"] and x["status"] == "approved" for x in values))
            menu(manager_page, "管理看板"); menu(manager_page, "公告审核发布")
            choose(manager_page, "公告", f"{title}（approved）")
            manager_page.get_by_role("button", name="人工发布").click()
            poll(manager, "/api/v1/announcements", lambda values: any(x["id"] == announcement["id"] and x["status"] == "published" for x in values))
            manager_page.screenshot(path=str(OUT / "announcement_published.png"), full_page=True)
            report["scenarios"].append({"name": "draft-review-publish announcement in UI", "evidence_type": "browser_business_flow", "status": "PASS"})

            resident_context.tracing.stop(path=str(OUT / "browser_business_trace.zip"))
            resident_context.close()
            browser.close()

        report.update({
            "status": "PASS",
            "artifacts": ["resident_created_work_order.png", "work_order_completed.png", "announcement_published.png", "browser_business_trace.zip"],
            "browser_business_flows": sum(x["evidence_type"] == "browser_business_flow" for x in report["scenarios"]),
        })
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        for process in (web, api):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
        api_log.close(); web_log.close()
        if report.get("status") != "PASS":
            report["api_log_tail"] = api_log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
            report["web_log_tail"] = web_log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        shutil.rmtree(runtime, ignore_errors=True)

    (OUT / "stage5_e2e_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "docs/52_stage5_e2e_test_report.md").write_text(
        "# 阶段 5 浏览器 E2E 报告\n\n"
        "仅 `browser_business_flow` 表示经页面完成的业务操作；API 检查单独标识。\n\n"
        "```json\n" + json.dumps(report, ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

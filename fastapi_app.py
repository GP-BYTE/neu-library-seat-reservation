import contextlib
import io
import json
import logging
import os
import queue
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import cancel_record
import load
import main
import manage_user
from session_set import create_session


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
CACHE_DIR = ROOT_DIR / "cache"
HISTORY_FILE = CACHE_DIR / "history.json"
TEMPLATE_FILE = CACHE_DIR / "templates.json"


def generate_time_options() -> List[str]:
    options = []
    start_time = datetime.strptime("08:00:00", "%H:%M:%S")
    end_time = datetime.strptime("22:00:00", "%H:%M:%S")
    current_time = start_time
    while current_time <= end_time:
        options.append(current_time.strftime("%H:%M:%S"))
        current_time += timedelta(minutes=20)
    return options


TIME_OPTIONS = generate_time_options()


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def write_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def load_history_records() -> List[Dict[str, Any]]:
    data = read_json_file(HISTORY_FILE, [])
    return data if isinstance(data, list) else []


def save_history_records(records: List[Dict[str, Any]]) -> None:
    write_json_file(HISTORY_FILE, records)


def load_templates() -> Dict[str, Dict[str, Any]]:
    data = read_json_file(TEMPLATE_FILE, {})
    return data if isinstance(data, dict) else {}


def save_templates(templates: Dict[str, Dict[str, Any]]) -> None:
    write_json_file(TEMPLATE_FILE, templates)


def public_reservation_info(reservation_info: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in reservation_info.items() if key != "密码"}


def client_reservation_info(reservation_info: Dict[str, Any]) -> Dict[str, Any]:
    public_info = public_reservation_info(reservation_info)
    public_info["passwordCached"] = bool(manage_user.has_user(str(reservation_info.get("学号", ""))))
    public_info["passwordProvided"] = bool(reservation_info.get("密码"))
    return public_info


def history_label(record: Dict[str, Any]) -> str:
    return f"{record['学号']} | {record['座位号']} | {record['开始时间']}-{record['结束时间']}"


def split_aim_string(order_string: str) -> Tuple[str, str]:
    translate_dic = {
        "216": "书库阅览区",
        "207": "书库阅览区",
        "307": "书库阅览区",
        "311": "书库阅览区",
        "313": "书库阅览区",
        "316": "书库阅览区",
        "211": "学习阅览区",
        "213": "学习阅览区",
    }
    region = order_string[0:3]
    aim_region = translate_dic.get(region)
    if aim_region is None:
        return "书库阅览区", ""
    return aim_region, region


def add_history_record(reservation_info: Dict[str, Any]) -> None:
    records = load_history_records()
    key = (
        reservation_info["学号"],
        reservation_info["座位号"],
        reservation_info["开始时间"],
        reservation_info["结束时间"],
    )
    for record in records:
        if (
            record.get("学号"),
            record.get("座位号"),
            record.get("开始时间"),
            record.get("结束时间"),
        ) == key:
            return
    records.append(public_reservation_info(reservation_info))
    save_history_records(records)


def record_choices(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    choices = []
    for record in records:
        record_id = str(record.get("id", ""))
        label = f"{record.get('seatNum', '')} | {record.get('startTime', '')} | {record.get('statusName', '')}"
        choices.append({"label": label, "value": record_id})
    return choices


def check_account_cache_status(usernumber: str) -> str:
    if not usernumber:
        return ""
    if not re.match(r"^\d{11}$", usernumber):
        return "请输入11位学号"
    if manage_user.has_user(usernumber):
        return "无需输入"
    return "需要输入"


def get_user_session_and_token(usernumber: str, password: str, action_name: str = "操作"):
    if not re.match(r"^\d{11}$", usernumber or ""):
        raise ValueError("请输入11位学号")
    if not password and not manage_user.has_user(usernumber):
        raise ValueError(
            f"{usernumber} 本地没有缓存密码，{action_name}前请填写该账号密码。"
            "不能复用其他账号的登录状态。"
        )
    user_session = create_session()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            encode_pwd = manage_user.main(usernumber, password=password or None, interactive=False)
        token = load.get_user_token(usernumber, encode_pwd, user_session)
        if not token:
            raise ValueError("登录失败，请检查账号或密码")
        return user_session, token
    except Exception:
        user_session.close()
        raise


class QueueLogStream:
    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue
        self.buffer = ""

    def write(self, text: str) -> None:
        if not text:
            return
        self.buffer += ANSI_ESCAPE_RE.sub("", text)
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                self.log_queue.put(line)

    def flush(self) -> None:
        if self.buffer.strip():
            self.log_queue.put(self.buffer.strip())
        self.buffer = ""


class AppLogStream:
    def __init__(self) -> None:
        self.buffer = ""

    def write(self, text: str) -> None:
        if not text:
            return
        self.buffer += ANSI_ESCAPE_RE.sub("", text)
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            app_state.append_log(line)

    def flush(self) -> None:
        if self.buffer.strip():
            app_state.append_log(self.buffer.strip())
        self.buffer = ""


class AppState:
    def __init__(self) -> None:
        self.reservation_list: List[Dict[str, Any]] = []
        self.reservation_stop_event = threading.Event()
        self.prepared_contexts: List[Any] = []
        self.prepared_signature: Optional[tuple] = None
        self.prepared_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.run_lock = threading.Lock()
        self.run_thread: Optional[threading.Thread] = None
        self.run_status = "idle"
        self.run_log: List[str] = []

    def append_log(self, message: str) -> None:
        message = ANSI_ESCAPE_RE.sub("", str(message)).strip()
        if not message:
            return
        with self.state_lock:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.run_log.append(f"[{timestamp}] {message}")
            if len(self.run_log) > 500:
                self.run_log = self.run_log[-500:]

    def set_status(self, status: str) -> None:
        with self.state_lock:
            self.run_status = status

    def reset_run_log(self, initial: str) -> None:
        with self.state_lock:
            self.run_log = []
        self.append_log(initial)


app_state = AppState()


class ReservationInput(BaseModel):
    usernumber: str
    password: str = ""
    seat_number: str
    start_time: str
    end_time: str


class HistoryInput(BaseModel):
    label: str


class TemplateInput(BaseModel):
    name: str


class AccountInput(BaseModel):
    usernumber: str
    password: str = ""


class CancelInput(BaseModel):
    usernumber: str
    password: str = ""
    record_id: str


def build_thread_args_list() -> List[tuple]:
    thread_args_list = []
    for res in app_state.reservation_list:
        args = (
            res["学号"],
            res["区域名称"],
            res["区域编号"],
            res["座位号"],
            res["开始时间"],
            res["结束时间"],
            None,
            False,
            res.get("密码") or None,
            False,
        )
        thread_args_list.append(args)
    return thread_args_list


def reservation_signature(thread_args_list: Optional[List[tuple]] = None) -> tuple:
    if thread_args_list is None:
        thread_args_list = build_thread_args_list()
    return tuple(thread_args_list)


def invalidate_prepared_reservations() -> None:
    with app_state.prepared_lock:
        if app_state.prepared_contexts:
            main.close_prepared_contexts(app_state.prepared_contexts)
        app_state.prepared_contexts = []
        app_state.prepared_signature = None


def take_prepared_reservations(thread_args_list: List[tuple]) -> Optional[List[Any]]:
    signature = reservation_signature(thread_args_list)
    with app_state.prepared_lock:
        if app_state.prepared_contexts and app_state.prepared_signature == signature:
            contexts = app_state.prepared_contexts
            app_state.prepared_contexts = []
            app_state.prepared_signature = None
            return contexts
    return None


def validate_reservation_ready() -> Optional[str]:
    if not app_state.reservation_list:
        return "请先添加预约信息"
    missing_password_users = [
        res["学号"]
        for res in app_state.reservation_list
        if not res.get("密码") and not manage_user.has_user(res["学号"])
    ]
    if missing_password_users:
        users = "、".join(sorted(set(missing_password_users)))
        return f"以下账号本地还没有缓存密码，请在前端填写密码后再添加预约：{users}"
    return None


def add_reservation(item: ReservationInput) -> Dict[str, Any]:
    if not re.match(r"^\d{11}$", item.usernumber):
        raise ValueError("学号格式错误，请输入11位数字学号")
    if item.start_time not in TIME_OPTIONS or item.end_time not in TIME_OPTIONS:
        raise ValueError("请选择有效的开始时间和结束时间")
    if item.start_time >= item.end_time:
        raise ValueError("结束时间必须晚于开始时间")
    seat_number = item.seat_number.strip()
    if not seat_number:
        raise ValueError("请输入座位号")
    aim_region, region = split_aim_string(seat_number)
    reservation_info = {
        "学号": item.usernumber.strip(),
        "座位号": seat_number,
        "区域编号": region,
        "区域名称": aim_region,
        "开始时间": item.start_time,
        "结束时间": item.end_time,
        "密码": item.password or "",
    }
    app_state.reservation_list.append(reservation_info)
    add_history_record(reservation_info)
    invalidate_prepared_reservations()
    return reservation_info


def add_public_reservation(item: Dict[str, Any]) -> Dict[str, Any]:
    return add_reservation(
        ReservationInput(
            usernumber=str(item.get("学号", "")).strip(),
            password="",
            seat_number=str(item.get("座位号", "")).strip(),
            start_time=str(item.get("开始时间", "")).strip(),
            end_time=str(item.get("结束时间", "")).strip(),
        )
    )


def capture_logs(fn):
    log_queue: queue.Queue = queue.Queue()
    log_stream = QueueLogStream(log_queue)
    root_logger = logging.getLogger()
    old_handlers = root_logger.handlers[:]
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    root_logger.handlers = [handler]
    try:
        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
            result = fn()
    finally:
        log_stream.flush()
        root_logger.handlers = old_handlers

    lines = []
    while not log_queue.empty():
        lines.append(log_queue.get())
    return result, lines


def normalize_submit_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        raw_result = result.get("result", result.get("msg", result.get("message", "")))
        ok = bool(result.get("ok")) or raw_result == "success"
        return {
            "usernumber": str(result.get("usernumber", "")),
            "seat": str(result.get("set_id", result.get("seat", ""))),
            "start_time": str(result.get("start_time", "")),
            "end_time": str(result.get("end_time", "")),
            "result": raw_result,
            "ok": ok,
            "error": bool(result.get("error")),
        }
    return {
        "usernumber": "",
        "seat": "",
        "start_time": "",
        "end_time": "",
        "result": result,
        "ok": result == "success",
        "error": False,
    }


def summarize_submit_results(results: Any) -> Dict[str, Any]:
    normalized = [normalize_submit_result(result) for result in (results or [])]
    total = len(normalized)
    success_count = sum(1 for result in normalized if result["ok"])
    failures = [result for result in normalized if not result["ok"]]
    return {
        "results": normalized,
        "total": total,
        "success_count": success_count,
        "failure_count": total - success_count,
        "failures": failures,
        "all_success": total > 0 and success_count == total,
    }


def failed_reservations_from_results(
    pending_reservations: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    success_keys = {
        (
            result.get("usernumber", ""),
            result.get("seat", ""),
            result.get("start_time", ""),
            result.get("end_time", ""),
        )
        for result in summary.get("results", [])
        if result.get("ok")
    }
    if not success_keys:
        return pending_reservations
    return [
        reservation
        for reservation in pending_reservations
        if (
            str(reservation.get("学号", "")),
            str(reservation.get("座位号", "")),
            str(reservation.get("开始时间", "")),
            str(reservation.get("结束时间", "")),
        )
        not in success_keys
    ]


def failure_summary_line(summary: Dict[str, Any]) -> str:
    details = []
    for failure in summary.get("failures", [])[:3]:
        target = " ".join(
            part
            for part in [
                failure.get("usernumber", ""),
                failure.get("seat", ""),
                f"{failure.get('start_time', '')}-{failure.get('end_time', '')}".strip("-"),
            ]
            if part
        )
        result = failure.get("result", "未知失败")
        details.append(f"{target or '预约任务'}：{result}")
    if not details:
        details.append("未收到有效提交结果")
    return "；".join(details)


def run_with_frontend_logs(thread_args_list: List[tuple], stop_event=None) -> List[Dict[str, Any]]:
    log_stream = AppLogStream()
    root_logger = logging.getLogger()
    old_handlers = root_logger.handlers[:]
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    root_logger.handlers = [handler]

    try:
        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
            result = main.thread_run(*thread_args_list, stop_event=stop_event)
            log_stream.flush()
            return result or []
    finally:
        log_stream.flush()
        root_logger.handlers = old_handlers


def run_prepared_with_frontend_logs(contexts: List[Any], stop_event=None) -> List[Dict[str, Any]]:
    log_stream = AppLogStream()
    root_logger = logging.getLogger()
    old_handlers = root_logger.handlers[:]
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    root_logger.handlers = [handler]

    try:
        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
            try:
                should_wait = all(getattr(context, "user_defind_time", None) is None for context in contexts)
                if should_wait:
                    stopped = main.wait_until_reservation_start(stop_event=stop_event)
                    if stopped:
                        return []
                return main.thread_submit_prepared(contexts, stop_event=stop_event) or []
            finally:
                main.close_prepared_contexts(contexts)
            log_stream.flush()
    finally:
        log_stream.flush()
        root_logger.handlers = old_handlers


def current_state(extra_message: str = "") -> Dict[str, Any]:
    history = load_history_records()
    templates = load_templates()
    users = manage_user.list_users()
    with app_state.state_lock:
        run_status = app_state.run_status
        run_log = list(app_state.run_log)
    with app_state.prepared_lock:
        prepared_count = len(app_state.prepared_contexts)
    return {
        "message": extra_message,
        "timeOptions": TIME_OPTIONS,
        "targetTime": main.RESERVATION_TARGET_TIME,
        "runStatus": run_status,
        "runLog": run_log,
        "preparedCount": prepared_count,
        "reservations": [client_reservation_info(item) for item in app_state.reservation_list],
        "history": [{"label": history_label(record), "item": record} for record in history],
        "templates": [
            {
                "name": name,
                "created_at": value.get("created_at", ""),
                "updated_at": value.get("updated_at", ""),
                "count": len(value.get("items", [])) if isinstance(value, dict) else 0,
            }
            for name, value in sorted(templates.items())
            if isinstance(value, dict)
        ],
        "accounts": users,
    }


app = FastAPI(title="NEU Library Seat Reservation", version="4.0.5")
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


@app.middleware("http")
async def no_cache_frontend_assets(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/web/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/state")
def api_state():
    return current_state()


@app.get("/api/account/status")
def api_account_status(usernumber: str = ""):
    return {"status": check_account_cache_status(usernumber.strip())}


@app.post("/api/reservations")
def api_add_reservation(item: ReservationInput):
    try:
        reservation_info = add_reservation(item)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return current_state(f"已添加预约：{reservation_info['学号']} {reservation_info['座位号']}")


@app.delete("/api/reservations")
def api_clear_reservations():
    invalidate_prepared_reservations()
    app_state.reservation_list.clear()
    return current_state("已清空所有预约信息")


@app.post("/api/history/load")
def api_load_history(item: HistoryInput):
    history = load_history_records()
    target = next((record for record in history if history_label(record) == item.label), None)
    if not target:
        raise HTTPException(status_code=404, detail="历史记录不存在，请刷新后重试")
    try:
        reservation_info = add_public_reservation(target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return current_state(f"已从历史记录添加：{reservation_info['学号']} {reservation_info['座位号']}")


@app.delete("/api/history")
def api_clear_history():
    save_history_records([])
    return current_state("已清空历史记录")


@app.post("/api/templates")
def api_save_template(item: TemplateInput):
    name = item.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="请先输入模板名称")
    if not app_state.reservation_list:
        raise HTTPException(status_code=400, detail="请先添加至少一条预约信息")
    templates = load_templates()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old_template = templates.get(name)
    created_at = old_template.get("created_at") if isinstance(old_template, dict) else None
    templates[name] = {
        "name": name,
        "created_at": created_at or now,
        "updated_at": now,
        "items": [public_reservation_info(reservation) for reservation in app_state.reservation_list],
    }
    save_templates(templates)
    return current_state(f"已保存模板：{name}，共 {len(app_state.reservation_list)} 条预约")


@app.post("/api/templates/load")
def api_load_template(item: TemplateInput):
    name = item.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="请先选择模板")
    template = load_templates().get(name)
    if not isinstance(template, dict):
        raise HTTPException(status_code=404, detail=f"模板不存在：{name}")
    items = template.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail=f"模板为空：{name}")
    invalidate_prepared_reservations()
    added = 0
    for template_item in items:
        if not isinstance(template_item, dict):
            continue
        try:
            add_public_reservation(template_item)
        except ValueError:
            continue
        added += 1
    if not added:
        raise HTTPException(status_code=400, detail=f"模板没有可加载的预约信息：{name}")
    return current_state(
        f"已加载模板：{name}，新增 {added} 条预约。模板不会保存密码，请确保账号已有密码缓存。"
    )


@app.post("/api/templates/delete")
def api_delete_template(item: TemplateInput):
    name = item.name.strip()
    templates = load_templates()
    if not name:
        raise HTTPException(status_code=400, detail="请先选择模板")
    if name not in templates:
        raise HTTPException(status_code=404, detail=f"模板不存在：{name}")
    invalidate_prepared_reservations()
    del templates[name]
    save_templates(templates)
    return current_state(f"已删除模板：{name}")


@app.post("/api/preheat")
def api_preheat():
    if app_state.run_status == "running":
        raise HTTPException(status_code=409, detail="预约任务运行中，不能重复预热")
    app_state.reservation_stop_event.clear()
    error = validate_reservation_ready()
    if error:
        raise HTTPException(status_code=400, detail=error)
    thread_args_list = build_thread_args_list()
    signature = reservation_signature(thread_args_list)
    app_state.reset_run_log("开始预热预约信息...")
    app_state.set_status("preheating")
    contexts = []
    try:
        def work():
            return main.prepare_thread_contexts(*thread_args_list, stop_event=app_state.reservation_stop_event)

        contexts, log_lines = capture_logs(work)
        for line in log_lines:
            app_state.append_log(line)
        if app_state.reservation_stop_event.is_set():
            main.close_prepared_contexts(contexts)
            app_state.set_status("stopped")
            app_state.append_log("已停止预热")
            return current_state("已停止预热")
        if not contexts:
            app_state.set_status("error")
            app_state.append_log("预热未生成可用预约任务")
            return current_state("预热未生成可用预约任务")
        with app_state.prepared_lock:
            if app_state.prepared_contexts:
                main.close_prepared_contexts(app_state.prepared_contexts)
            app_state.prepared_contexts = contexts
            app_state.prepared_signature = signature
        app_state.set_status("idle")
        app_state.append_log(f"预热完成，共 {len(contexts)} 条预约信息已就绪。")
        return current_state(f"预热完成，共 {len(contexts)} 条预约信息已就绪。")
    except Exception as exc:
        main.close_prepared_contexts(contexts)
        app_state.set_status("error")
        app_state.append_log(f"预热失败：{exc}")
        raise HTTPException(status_code=500, detail=f"预热失败：{exc}") from exc


@app.post("/api/start")
def api_start():
    if app_state.run_thread and app_state.run_thread.is_alive():
        raise HTTPException(status_code=409, detail="预约任务已在运行")
    app_state.reservation_stop_event.clear()
    error = validate_reservation_ready()
    if error:
        raise HTTPException(status_code=400, detail=error)

    thread_args_list = build_thread_args_list()
    contexts = take_prepared_reservations(thread_args_list)
    pending_reservations = list(app_state.reservation_list)
    app_state.reset_run_log("开始预约...")
    app_state.set_status("running")

    def worker() -> None:
        should_clear_reservations = False
        try:
            submit_results = []
            if contexts:
                app_state.append_log("使用已预热的预约信息")
                submit_results = run_prepared_with_frontend_logs(
                    contexts,
                    stop_event=app_state.reservation_stop_event,
                )
            else:
                app_state.append_log("未发现可复用预热信息，正在自动预热")
                submit_results = run_with_frontend_logs(
                    thread_args_list,
                    stop_event=app_state.reservation_stop_event,
                )
            if app_state.reservation_stop_event.is_set():
                app_state.set_status("stopped")
                app_state.append_log("已停止预约")
            else:
                summary = summarize_submit_results(submit_results)
                if summary["all_success"]:
                    should_clear_reservations = True
                    app_state.set_status("done")
                    app_state.append_log(
                        f"预约完成：成功 {summary['success_count']}/{summary['total']} 条。"
                    )
                else:
                    app_state.set_status("error")
                    app_state.reservation_list[:] = failed_reservations_from_results(
                        pending_reservations,
                        summary,
                    )
                    app_state.append_log(
                        f"预约未全部成功：成功 {summary['success_count']}/{summary['total']} 条，"
                        f"失败 {summary['failure_count']} 条。{failure_summary_line(summary)}"
                    )
                    app_state.append_log("未成功的预约已保留在列表中，可检查日志后重试。")
        except Exception as exc:
            app_state.set_status("error")
            app_state.append_log(f"预约过程中出现错误：{exc}")
            app_state.reservation_list[:] = pending_reservations
            app_state.append_log("预约列表已保留，请修正后重试。")
        finally:
            if should_clear_reservations:
                app_state.reservation_list.clear()

    app_state.run_thread = threading.Thread(target=worker, daemon=True)
    app_state.run_thread.start()
    return current_state("预约任务已启动")


@app.post("/api/stop")
def api_stop():
    app_state.reservation_stop_event.set()
    app_state.append_log("已发送停止请求，正在结束当前预约任务")
    return current_state("已发送停止请求")


@app.post("/api/records/query")
def api_query_records(item: AccountInput):
    try:
        user_session, token = get_user_session_and_token(item.usernumber.strip(), item.password, action_name="查询预约")
        try:
            records = cancel_record.get_record_list(token, user_session)
        finally:
            user_session.close()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"查询失败：{exc}") from exc
    return {
        **current_state(f"查询完成，共 {len(records)} 条记录"),
        "records": records,
        "recordChoices": record_choices(records),
    }


@app.post("/api/records/cancel")
def api_cancel_record(item: CancelInput):
    if not item.record_id:
        raise HTTPException(status_code=400, detail="请先选择一条预约记录")
    try:
        user_session, token = get_user_session_and_token(item.usernumber.strip(), item.password, action_name="取消预约")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                ok = cancel_record.Cancel_Site(token, item.record_id, user_session)
            records = cancel_record.get_record_list(token, user_session)
        finally:
            user_session.close()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"取消失败：{exc}") from exc
    message = "取消成功，已刷新当前预约" if ok else "取消请求未成功，请刷新后确认状态"
    return {
        **current_state(message),
        "records": records,
        "recordChoices": record_choices(records),
    }


@app.post("/api/accounts/delete")
def api_delete_account(item: AccountInput):
    usernumber = item.usernumber.strip()
    if not usernumber:
        raise HTTPException(status_code=400, detail="请先选择要下线的账号")
    invalidate_prepared_reservations()
    deleted = manage_user.delete_user(usernumber)
    message = f"已下线账号：{usernumber}" if deleted else f"账号不存在：{usernumber}"
    return current_state(message)


@app.delete("/api/accounts")
def api_clear_accounts():
    invalidate_prepared_reservations()
    cleared = manage_user.clear_users()
    message = "已下线所有账号" if cleared else "当前没有已缓存账号"
    return current_state(message)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("FASTAPI_SERVER_PORT", "8000"))
    uvicorn.run("fastapi_app:app", host="127.0.0.1", port=port)

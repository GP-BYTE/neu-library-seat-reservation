import os
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
import gradio as gr
import re
import main
import manage_user
import load
import cancel_record
from session_set import create_session
import threading
import time
import json
import contextlib
import logging
import queue
import html
import io
from datetime import datetime, timedelta

ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')

# 生成20分钟间隔的时间选项
def generate_time_options():
    options = []
    start_time = datetime.strptime("08:00:00", "%H:%M:%S")
    end_time = datetime.strptime("22:00:00", "%H:%M:%S")
    
    current_time = start_time
    while current_time <= end_time:
        time_str = current_time.strftime("%H:%M:%S")
        options.append(time_str)
        current_time += timedelta(minutes=20)
    return options

# 时间选项
TIME_OPTIONS = generate_time_options()

def get_server_port():
    configured_port = os.environ.get("GRADIO_SERVER_PORT")
    if configured_port:
        return int(configured_port)
    return None

# 存储预约信息的列表
reservation_list = []
reservation_stop_event = threading.Event()
prepared_contexts = []
prepared_signature = None
prepared_lock = threading.Lock()
# 存储历史预约记录
HISTORY_FILE = os.path.join("cache", "history.json")
TEMPLATE_FILE = os.path.join("cache", "templates.json")

def load_history_records():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []

def save_history_records(records=None):
    if records is None:
        records = history_records
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    temp_path = f"{HISTORY_FILE}.tmp"
    with open(temp_path, "w") as f:
        json.dump(records, f)
    os.replace(temp_path, HISTORY_FILE)

history_records = load_history_records()

def load_templates():
    if not os.path.exists(TEMPLATE_FILE):
        return {}
    try:
        with open(TEMPLATE_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}

def save_templates(templates):
    os.makedirs(os.path.dirname(TEMPLATE_FILE), exist_ok=True)
    temp_path = f"{TEMPLATE_FILE}.tmp"
    with open(temp_path, "w") as f:
        json.dump(templates, f)
    os.replace(temp_path, TEMPLATE_FILE)

def template_names():
    return sorted(load_templates().keys())

def template_reservation_items():
    return [public_reservation_info(reservation) for reservation in reservation_list]

def history_label(record):
    return f"{record['学号']} | {record['座位号']} | {record['开始时间']}-{record['结束时间']}"

def public_reservation_info(reservation_info):
    return {key: value for key, value in reservation_info.items() if key != "密码"}

def build_thread_args_list():
    thread_args_list = []
    for res in reservation_list:
        args = (
            res['学号'],
            res['区域名称'],
            res['区域编号'],
            res['座位号'],
            res['开始时间'],
            res['结束时间'],
            None,
            False,
            res.get('密码') or None,
            False,
        )
        thread_args_list.append(args)
    return thread_args_list

def reservation_signature(thread_args_list=None):
    if thread_args_list is None:
        thread_args_list = build_thread_args_list()
    return tuple(thread_args_list)

def invalidate_prepared_reservations():
    global prepared_contexts, prepared_signature
    with prepared_lock:
        if prepared_contexts:
            main.close_prepared_contexts(prepared_contexts)
        prepared_contexts = []
        prepared_signature = None

def take_prepared_reservations(thread_args_list):
    global prepared_contexts, prepared_signature
    signature = reservation_signature(thread_args_list)
    with prepared_lock:
        if prepared_contexts and prepared_signature == signature:
            contexts = prepared_contexts
            prepared_contexts = []
            prepared_signature = None
            return contexts
    return None

def add_history_record(reservation_info):
    records = load_history_records()
    key = (reservation_info["学号"], reservation_info["座位号"], reservation_info["开始时间"], reservation_info["结束时间"])
    for record in records:
        if (record["学号"], record["座位号"], record["开始时间"], record["结束时间"]) == key:
            history_records[:] = records
            return
    records.append(public_reservation_info(reservation_info))
    history_records[:] = records
    save_history_records(records)

def format_history_options():
    return [history_label(record) for record in history_records]

def refresh_history_choices():
    global history_records
    history_records = load_history_records()
    return gr.update(choices=format_history_options())

def refresh_template_choices():
    names = template_names()
    return gr.update(choices=names, value=names[0] if names else None), "已刷新模板列表"

def save_current_template(template_name):
    name = str(template_name or "").strip()
    if not name:
        return gr.update(choices=template_names()), "请先输入模板名称"
    if not reservation_list:
        return gr.update(choices=template_names()), "请先添加至少一条预约信息"

    templates = load_templates()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old_template = templates.get(name)
    created_at = old_template.get("created_at") if isinstance(old_template, dict) else None
    created_at = created_at or now
    templates[name] = {
        "name": name,
        "created_at": created_at,
        "updated_at": now,
        "items": template_reservation_items(),
    }
    save_templates(templates)
    names = template_names()
    return gr.update(choices=names, value=name), f"已保存模板：{name}，共 {len(reservation_list)} 条预约"

def load_template_to_reservations(template_name):
    name = str(template_name or "").strip()
    if not name:
        return "请先选择模板", format_reservation_list(), gr.update(choices=format_history_options())

    template = load_templates().get(name)
    if not isinstance(template, dict):
        return f"模板不存在：{name}", format_reservation_list(), gr.update(choices=format_history_options())
    items = template.get("items")
    if not isinstance(items, list) or not items:
        return f"模板为空：{name}", format_reservation_list(), gr.update(choices=format_history_options())

    invalidate_prepared_reservations()
    added = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        usernumber = str(item.get("学号", "")).strip()
        seat_number = str(item.get("座位号", "")).strip()
        start_time = str(item.get("开始时间", "")).strip()
        end_time = str(item.get("结束时间", "")).strip()
        if not usernumber or not seat_number or not start_time or not end_time:
            continue
        add_reservation(usernumber, "", seat_number, start_time, end_time)
        added += 1

    if added == 0:
        return f"模板没有可加载的预约信息：{name}", format_reservation_list(), gr.update(choices=format_history_options())
    return (
        f"已加载模板：{name}，新增 {added} 条预约。模板不会保存密码，预热或开始预约前请确保账号已有密码缓存。",
        format_reservation_list(),
        gr.update(choices=format_history_options()),
    )

def delete_template(template_name):
    name = str(template_name or "").strip()
    if not name:
        return gr.update(choices=template_names(), value=None), "请先选择模板"
    templates = load_templates()
    if name not in templates:
        return gr.update(choices=template_names(), value=None), f"模板不存在：{name}"

    invalidate_prepared_reservations()
    del templates[name]
    save_templates(templates)
    names = template_names()
    return gr.update(choices=names, value=names[0] if names else None), f"已删除模板：{name}"

def check_account_cache_status(usernumber):
    if not usernumber:
        return "", gr.update(value="")
    if not re.match(r'^\d{11}$', usernumber):
        return "请输入11位学号", gr.update(value="")
    if manage_user.has_user(usernumber):
        return "无需输入", gr.update(value="")
    return "需要输入", gr.update(value="")

def get_user_session_and_token(usernumber, password, action_name="操作"):
    if not re.match(r'^\d{11}$', usernumber or ""):
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

def add_reservation(usernumber, password, seat_number, start_time, end_time):
    """添加预约信息到列表"""
    # 获取区域信息
    aim_region, region = splite_aim_string(seat_number)
    
    # 构造预约信息
    reservation_info = {
        "学号": usernumber,
        "座位号": seat_number,
        "区域编号": region,
        "区域名称": aim_region,
        "开始时间": start_time,
        "结束时间": end_time,
        "密码": password or "",
    }
    
    reservation_list.append(reservation_info)
    return reservation_info

def splite_aim_string(order_string):
    """根据座位号前三位确定区域"""
    translate_dic = {
        '216': '书库阅览区', '207': '书库阅览区', '307': '书库阅览区',
        "311": '书库阅览区', '313': '书库阅览区', '316': '书库阅览区',
        '211': '学习阅览区', '213': '学习阅览区'
    }
    try:
        region = order_string[0:3]
        aim_region = translate_dic[region]
    except KeyError:
        aim_region = '书库阅览区'
        region = ""
    return aim_region, region

def format_reservation_list():
    """格式化预约列表用于显示"""
    if not reservation_list:
        return "暂无预约信息"
    
    formatted = "预约信息列表：\n"
    for i, res in enumerate(reservation_list, 1):
        formatted += f"{i}. 学号: {res['学号']}, 座位: {res['座位号']}, 区域: {res['区域名称']}, 时间: {res['开始时间']}-{res['结束时间']}\n"
    return formatted

def add_reservation_to_list(usernumber, password, seat_number, start_time, end_time):
    """添加预约信息并更新显示"""
    # 验证学号格式: 11位数字
    if not re.match(r'^\d{11}$', usernumber):
        return "学号格式错误，请输入11位数字学号", format_reservation_list(), gr.update(choices=format_history_options())
    
    # 添加预约信息
    invalidate_prepared_reservations()
    reservation_info = add_reservation(usernumber, password, seat_number, start_time, end_time)
    add_history_record(reservation_info)
    
    info_text = f"已添加预约信息：\n学号: {reservation_info['学号']}\n座位号: {reservation_info['座位号']}\n区域: {reservation_info['区域名称']}\n时间: {start_time} - {end_time}"
    
    return info_text, format_reservation_list(), gr.update(choices=format_history_options())

def add_history_to_list(history_choice):
    """将历史记录添加到预约列表"""
    if not history_choice:
        return "请先选择一条历史记录", format_reservation_list()
    target = None
    for record in history_records:
        if history_label(record) == history_choice:
            target = record
            break
    if not target:
        return "历史记录不存在，请刷新后重试", format_reservation_list()
    invalidate_prepared_reservations()
    reservation_info = add_reservation(
        target["学号"],
        "",
        target["座位号"],
        target["开始时间"],
        target["结束时间"],
    )
    info_text = (
        "已从历史记录添加：\n"
        f"学号: {reservation_info['学号']}\n"
        f"座位号: {reservation_info['座位号']}\n"
        f"区域: {reservation_info['区域名称']}\n"
        f"时间: {reservation_info['开始时间']} - {reservation_info['结束时间']}"
    )
    return info_text, format_reservation_list()

def clear_history_records():
    history_records.clear()
    save_history_records([])
    return "已清空历史记录", gr.update(choices=format_history_options(), value=None)

def render_record_cards(records):
    if not records:
        return "<div style='padding: 14px; color: #666;'>暂无当前预约记录</div>"
    cards = []
    for record in records:
        record_id = html.escape(str(record.get("id", "")))
        seat = html.escape(str(record.get("seatNum", "")))
        status = html.escape(str(record.get("statusName", "")))
        start = html.escape(str(record.get("startTime", "")))
        end = html.escape(str(record.get("endTime", "")))
        cards.append(
            "<div style='border:1px solid #e5e7eb; border-radius:8px; padding:14px; margin:10px 0; background:#fff;'>"
            f"<div style='display:flex; justify-content:space-between; gap:12px; align-items:center;'>"
            f"<strong style='font-size:16px;'>座位 {seat}</strong>"
            f"<span style='font-size:13px; padding:3px 8px; border-radius:999px; background:#eef2ff; color:#3730a3;'>{status}</span>"
            "</div>"
            f"<div style='margin-top:8px; color:#374151;'>开始：{start}</div>"
            f"<div style='margin-top:4px; color:#374151;'>结束：{end}</div>"
            f"<div style='margin-top:4px; color:#6b7280; font-size:12px;'>记录ID：{record_id}</div>"
            "</div>"
        )
    return "".join(cards)

def record_choices(records):
    choices = []
    for record in records:
        record_id = str(record.get("id", ""))
        label = f"{record.get('seatNum', '')} | {record.get('startTime', '')} | {record.get('statusName', '')}"
        choices.append((label, record_id))
    return choices

def query_current_records(usernumber, password):
    try:
        user_session, token = get_user_session_and_token(usernumber, password, action_name="查询预约")
        try:
            records = cancel_record.get_record_list(token, user_session)
        finally:
            user_session.close()
    except Exception as e:
        return (
            f"<div style='padding:14px; color:#b91c1c;'>查询失败：{html.escape(str(e))}</div>",
            gr.update(choices=[], value=None),
            f"查询失败：{str(e)}",
        )

    choices = record_choices(records)
    return (
        render_record_cards(records),
        gr.update(choices=choices, value=choices[0][1] if choices else None),
        f"查询完成，共 {len(records)} 条记录",
    )

def cancel_selected_record(usernumber, password, selected_record_id):
    if not selected_record_id:
        return gr.update(), gr.update(choices=[], value=None), "请先选择一条预约记录"
    try:
        user_session, token = get_user_session_and_token(usernumber, password, action_name="取消预约")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                ok = cancel_record.Cancel_Site(token, selected_record_id, user_session)
            records = cancel_record.get_record_list(token, user_session)
        finally:
            user_session.close()
    except Exception as e:
        return gr.update(), gr.update(), f"取消失败：{str(e)}"

    choices = record_choices(records)
    message = "取消成功，已刷新当前预约" if ok else "取消请求未成功，请刷新后确认状态"
    return (
        render_record_cards(records),
        gr.update(choices=choices, value=choices[0][1] if choices else None),
        message,
    )

class QueueLogStream:
    def __init__(self, log_queue):
        self.log_queue = log_queue
        self.buffer = ""

    def write(self, text):
        if not text:
            return
        self.buffer += ANSI_ESCAPE_RE.sub("", text)
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                self.log_queue.put(line)

    def flush(self):
        if self.buffer.strip():
            self.log_queue.put(self.buffer.strip())
        self.buffer = ""

def run_with_frontend_logs(thread_args_list, log_queue, stop_event=None):
    log_stream = QueueLogStream(log_queue)
    root_logger = logging.getLogger()
    old_handlers = root_logger.handlers[:]
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.handlers = [handler]
    try:
        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
            main.thread_run(*thread_args_list, stop_event=stop_event)
    finally:
        log_stream.flush()
        root_logger.handlers = old_handlers

def run_prepared_with_frontend_logs(contexts, log_queue, stop_event=None):
    log_stream = QueueLogStream(log_queue)
    root_logger = logging.getLogger()
    old_handlers = root_logger.handlers[:]
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.handlers = [handler]
    try:
        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
            try:
                should_wait = all(getattr(context, 'user_defind_time', None) is None for context in contexts)
                if should_wait:
                    stopped = main.wait_until_reservation_start(stop_event=stop_event)
                    if stopped:
                        return
                main.thread_submit_prepared(contexts, stop_event=stop_event)
            finally:
                main.close_prepared_contexts(contexts)
    finally:
        log_stream.flush()
        root_logger.handlers = old_handlers

def capture_logs(fn):
    log_queue = queue.Queue()
    log_stream = QueueLogStream(log_queue)
    root_logger = logging.getLogger()
    old_handlers = root_logger.handlers[:]
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
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

def validate_reservation_ready():
    if not reservation_list:
        return "请先添加预约信息"
    missing_password_users = [
        res["学号"]
        for res in reservation_list
        if not res.get("密码") and not manage_user.has_user(res["学号"])
    ]
    if missing_password_users:
        users = "、".join(sorted(set(missing_password_users)))
        return f"以下账号本地还没有缓存密码，请在前端填写密码后再添加预约：{users}"
    return None

def preheat_reservations():
    """提前登录并解析座位映射，正式预约时直接提交。"""
    global prepared_contexts, prepared_signature
    reservation_stop_event.clear()
    error = validate_reservation_ready()
    if error:
        return error

    thread_args_list = build_thread_args_list()
    signature = reservation_signature(thread_args_list)
    output_lines = ["开始预热预约信息..."]
    contexts = []
    try:
        def work():
            return main.prepare_thread_contexts(*thread_args_list, stop_event=reservation_stop_event)

        contexts, log_lines = capture_logs(work)
        output_lines.extend(log_lines)
        if reservation_stop_event.is_set():
            main.close_prepared_contexts(contexts)
            return "\n".join(output_lines + ["已停止预热"])
        if not contexts:
            return "\n".join(output_lines + ["预热未生成可用预约任务"])

        with prepared_lock:
            if prepared_contexts:
                main.close_prepared_contexts(prepared_contexts)
            prepared_contexts = contexts
            prepared_signature = signature
        return "\n".join(output_lines + [f"预热完成，共 {len(contexts)} 条预约信息已就绪。"])
    except Exception as e:
        main.close_prepared_contexts(contexts)
        return "\n".join(output_lines + [f"预热失败：{str(e)}"])

def start_reservation():
    """开始预约"""
    global reservation_list
    reservation_stop_event.clear()
    error = validate_reservation_ready()
    if error:
        yield error, format_reservation_list()
        return
    
    thread_args_list = build_thread_args_list()
    contexts = take_prepared_reservations(thread_args_list)
    pending_reservations = list(reservation_list)
    
    log_queue = queue.Queue()
    done = threading.Event()
    should_clear_reservations = threading.Event()
    output_lines = ["开始预约..."]

    def worker():
        try:
            if contexts:
                log_queue.put("使用已预热的预约信息")
                should_clear_reservations.set()
                run_prepared_with_frontend_logs(contexts, log_queue, stop_event=reservation_stop_event)
            else:
                log_queue.put("未发现可复用预热信息，正在自动预热")
                run_with_frontend_logs(thread_args_list, log_queue, stop_event=reservation_stop_event)
                should_clear_reservations.set()
            if reservation_stop_event.is_set():
                log_queue.put("已停止预约")
            else:
                log_queue.put("预约完成！")
        except Exception as e:
            log_queue.put(f"预约过程中出现错误: {str(e)}")
        finally:
            done.set()

    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()

    while not done.is_set() or not log_queue.empty():
        while not log_queue.empty():
            output_lines.append(log_queue.get())
        yield "\n".join(output_lines), format_reservation_list()
        if not done.is_set():
            time.sleep(0.5)

    if should_clear_reservations.is_set():
        reservation_list.clear()
        yield "\n".join(output_lines), format_reservation_list()
    else:
        reservation_list[:] = pending_reservations
        yield "\n".join(output_lines + ["预约列表已保留，请修正后重试。"]), format_reservation_list()

def clear_reservations():
    """清空预约列表"""
    invalidate_prepared_reservations()
    reservation_list.clear()
    return "已清空所有预约信息", "暂无预约信息"

def stop_reservation():
    reservation_stop_event.set()
    return "已发送停止请求，正在结束当前预约任务..."

def format_cached_accounts():
    users = manage_user.list_users()
    if not users:
        return "暂无已缓存账号"
    lines = [f"已缓存账号共 {len(users)} 个："]
    lines.extend(f"{index}. {usernumber}" for index, usernumber in enumerate(users, 1))
    return "\n".join(lines)

def refresh_account_manager():
    users = manage_user.list_users()
    return (
        format_cached_accounts(),
        gr.update(choices=users, value=users[0] if users else None),
        "已刷新账号列表",
    )

def delete_cached_account(selected_usernumber, current_usernumber):
    if not selected_usernumber:
        status, password_update = check_account_cache_status(current_usernumber)
        return (
            format_cached_accounts(),
            gr.update(choices=manage_user.list_users(), value=None),
            "请先选择要下线的账号",
            status,
            password_update,
        )

    invalidate_prepared_reservations()
    deleted = manage_user.delete_user(selected_usernumber)
    users = manage_user.list_users()
    status, password_update = check_account_cache_status(current_usernumber)
    message = f"已下线账号：{selected_usernumber}" if deleted else f"账号不存在：{selected_usernumber}"
    return (
        format_cached_accounts(),
        gr.update(choices=users, value=users[0] if users else None),
        message,
        status,
        password_update,
    )

def clear_cached_accounts(current_usernumber):
    invalidate_prepared_reservations()
    cleared = manage_user.clear_users()
    status, password_update = check_account_cache_status(current_usernumber)
    message = "已下线所有账号" if cleared else "当前没有已缓存账号"
    return (
        format_cached_accounts(),
        gr.update(choices=[], value=None),
        message,
        status,
        password_update,
    )

# 创建Gradio界面
with gr.Blocks(title="图书馆座位预约系统") as demo:
    gr.Markdown("# 📚 图书馆座位预约系统")
    gr.Markdown("### 账号信息")
    with gr.Row():
        usernumber = gr.Textbox(
            label="学号",
            placeholder="请输入11位学号",
            max_lines=1
        )

        password = gr.Textbox(
            label="密码",
            placeholder="状态为“需要输入”时填写",
            type="password",
            max_lines=1
        )

        cache_status = gr.Textbox(
            label="密码缓存状态",
            value="",
            interactive=False,
            max_lines=1,
        )

    usernumber.change(
        fn=check_account_cache_status,
        inputs=[usernumber],
        outputs=[cache_status, password],
    )

    with gr.Tabs():
        with gr.Tab("预约座位"):
            gr.Markdown("### 请输入座位信息进行预约")
            gr.Markdown("历史记录会在添加预约信息时自动保存到本地。")
            with gr.Row():
                with gr.Column():
                    seat_number = gr.Textbox(
                        label="座位号",
                        placeholder="例如：21624B",
                        max_lines=1
                    )
                    
                    with gr.Row():
                        start_time = gr.Dropdown(
                            choices=TIME_OPTIONS,
                            value="08:00:00",
                            label="开始时间"
                        )
                        
                    end_time = gr.Dropdown(
                            choices=TIME_OPTIONS,
                            value="10:00:00",
                            label="结束时间"
                        )
                    
                    add_btn = gr.Button("添加预约信息", variant="primary")
                    preheat_btn = gr.Button("预热/检查预约")
                    start_btn = gr.Button("开始预约", variant="primary")
                    stop_btn = gr.Button("停止预约")
                    clear_btn = gr.Button("清空所有预约")
                    
                with gr.Column():
                    info_display = gr.Textbox(
                        label="当前预约信息",
                        interactive=False,
                        lines=6
                    )

                    history_choice = gr.Dropdown(
                        choices=format_history_options(),
                        label="历史记录",
                        interactive=True
                    )
                    history_add_btn = gr.Button("从历史记录加入预约列表")
                    history_clear_btn = gr.Button("清空历史记录")

                    template_name = gr.Textbox(
                        label="模板名称",
                        placeholder="例如：工作日常用座位",
                        max_lines=1,
                    )
                    template_choice = gr.Dropdown(
                        choices=template_names(),
                        label="预约模板",
                        interactive=True,
                    )
                    with gr.Row():
                        template_save_btn = gr.Button("保存当前列表为模板")
                        template_load_btn = gr.Button("加载模板")
                    with gr.Row():
                        template_refresh_btn = gr.Button("刷新模板")
                        template_delete_btn = gr.Button("删除模板")
                    template_output = gr.Textbox(
                        label="模板操作结果",
                        interactive=False,
                        lines=3,
                    )
                    
                    reservation_display = gr.Textbox(
                        label="预约信息列表",
                        interactive=False,
                        lines=10
                    )
                    
                    output_display = gr.Textbox(
                        label="程序输出",
                        interactive=False,
                        lines=8
                    )

        with gr.Tab("当前预约"):
            gr.Markdown("### 当前账号预约情况")
            current_records_html = gr.HTML(value=render_record_cards([]))
            current_record_choice = gr.Dropdown(
                choices=[],
                label="选择要取消的预约",
                interactive=True,
            )
            with gr.Row():
                query_records_btn = gr.Button("查询当前预约", variant="primary")
                cancel_record_btn = gr.Button("取消所选预约")
            current_records_output = gr.Textbox(
                label="操作结果",
                interactive=False,
                lines=5,
            )

        with gr.Tab("账号管理"):
            gr.Markdown("### 已缓存账号管理")
            cached_accounts_display = gr.Textbox(
                label="已缓存账号",
                value=format_cached_accounts(),
                interactive=False,
                lines=8,
            )
            cached_account_choice = gr.Dropdown(
                choices=manage_user.list_users(),
                label="选择要下线的账号",
                interactive=True,
            )
            with gr.Row():
                refresh_accounts_btn = gr.Button("刷新账号列表")
                delete_account_btn = gr.Button("下线所选账号")
                clear_accounts_btn = gr.Button("一键下线所有账号")
            account_manage_output = gr.Textbox(
                label="操作结果",
                interactive=False,
                lines=3,
            )

    # 设置按钮事件处理
    add_btn.click(
        fn=add_reservation_to_list,
        inputs=[usernumber, password, seat_number, start_time, end_time],
        outputs=[info_display, reservation_display, history_choice]
    )

    history_add_btn.click(
        fn=add_history_to_list,
        inputs=[history_choice],
        outputs=[info_display, reservation_display]
    )

    history_clear_btn.click(
        fn=clear_history_records,
        outputs=[info_display, history_choice]
    )

    template_save_btn.click(
        fn=save_current_template,
        inputs=[template_name],
        outputs=[template_choice, template_output]
    )

    template_load_btn.click(
        fn=load_template_to_reservations,
        inputs=[template_choice],
        outputs=[info_display, reservation_display, history_choice]
    )

    template_refresh_btn.click(
        fn=refresh_template_choices,
        outputs=[template_choice, template_output]
    )

    template_delete_btn.click(
        fn=delete_template,
        inputs=[template_choice],
        outputs=[template_choice, template_output]
    )

    preheat_btn.click(
        fn=preheat_reservations,
        outputs=[output_display]
    )

    demo.load(
        fn=refresh_history_choices,
        outputs=[history_choice]
    )

    demo.load(
        fn=refresh_account_manager,
        outputs=[cached_accounts_display, cached_account_choice, account_manage_output]
    )

    demo.load(
        fn=refresh_template_choices,
        outputs=[template_choice, template_output]
    )
    
    start_btn.click(
        fn=start_reservation,
        outputs=[output_display, reservation_display]
    )
    
    clear_btn.click(
        fn=clear_reservations,
        outputs=[info_display, reservation_display]
    )

    stop_btn.click(
        fn=stop_reservation,
        outputs=[output_display]
    )

    query_records_btn.click(
        fn=query_current_records,
        inputs=[usernumber, password],
        outputs=[current_records_html, current_record_choice, current_records_output],
    )

    cancel_record_btn.click(
        fn=cancel_selected_record,
        inputs=[usernumber, password, current_record_choice],
        outputs=[current_records_html, current_record_choice, current_records_output],
    )

    refresh_accounts_btn.click(
        fn=refresh_account_manager,
        outputs=[cached_accounts_display, cached_account_choice, account_manage_output],
    )

    delete_account_btn.click(
        fn=delete_cached_account,
        inputs=[cached_account_choice, usernumber],
        outputs=[cached_accounts_display, cached_account_choice, account_manage_output, cache_status, password],
    )

    clear_accounts_btn.click(
        fn=clear_cached_accounts,
        inputs=[usernumber],
        outputs=[cached_accounts_display, cached_account_choice, account_manage_output, cache_status, password],
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=get_server_port(), share=False)

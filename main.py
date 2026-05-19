
import manage_user
# 导入load模块，可能用于加载用户令牌等操作
import load
# 导入requests库，用于发送HTTP请求
import requests
# 导入json库，用于处理JSON数据
import json
import build_set_and_id
import threading
import time
import traceback
import cancel_record
import random
import fancy_operation
from threading import Semaphore
from requests import session
import session_set
from session_set import create_session
from datetime import datetime

# 最佳实践是设置为2-3，根据服务器承受能力调整
MAX_CONCURRENT = 3
REQUEST_SEMAPHORE = Semaphore(MAX_CONCURRENT)

green = '\033[92m'
red = '\033[91m'
yellow = '\033[93m'
blue = '\033[94m'
end = '\033[0m'

import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MAX_FAILURE_COUNT = 3  # 可配置的失败次数阈值
RESERVATION_TARGET_TIME = '12:00:17'

def resolve_library_names(order_big_space_name, space_id_name):
    if space_id_name == '':
        return 'F6图书馆', 'F6图书室'
    return '华天图书馆', space_id_name + order_big_space_name

def close_prepared_contexts(contexts):
    for context in contexts:
        session_obj = getattr(context, 'session', None)
        if session_obj is not None:
            try:
                session_obj.close()
            except Exception:
                pass

def wait_until_reservation_start(target_time=RESERVATION_TARGET_TIME, stop_event=None):
    target_clock = datetime.strptime(target_time, '%H:%M:%S').time()
    last_logged_second = None
    while True:
        now = datetime.now()
        target = datetime.combine(now.date(), target_clock)
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return False

        current_second = now.strftime('%H:%M:%S')
        if current_second != last_logged_second:
            print(f'等待开始，目前时间是{current_second}，目标时间是{target_time}')
            last_logged_second = current_second

        sleep_for = min(1.0, max(0.02, remaining))
        if stop_event is not None:
            if stop_event.wait(sleep_for):
                print('已停止预约')
                return True
        else:
            time.sleep(sleep_for)

# 获取图书馆的代号，随机放入一个学号就可以
def get_id_liberary(user_token):
    """
    根据用户令牌获取图书馆的代号信息。

    :param user_token: 用户令牌，用于验证用户身份
    :return: 包含图书馆名称、uuid和value的列表
    """
    # 设置请求头，包含用户令牌、referer和user-agent信息
    headers = {
        'reader_token':user_token,
        'referer':'https://order.lib.nsu.edu.cn/',
        'user-agent':'Mozilla/5.0 (Linux; Android 14; V2307A Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240301 MMWEBID/4922 MicroMessenger/8.0.48.2580(0x28003052) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 Edg/131.0.0.0',
    }
    # 发送GET请求获取图书馆列表信息
    res = requests.get('https://order.lib.nsu.edu.cn/api/reader-no-filter/library/listCampus',headers=headers).text
    # 将返回的JSON字符串解析为Python字典
    de_json = json.loads(res)
    # 提取字典中的图书馆数据
    liberarys = de_json['data']
    # 初始化一个空列表，用于存储处理后的图书馆信息
    temp = []

    # 遍历图书馆数据列表
    for item in liberarys:
        # 初始化一个空字典，用于存储单个图书馆的信息
        temp_dir = {}
        # 将图书馆名称作为键，uuid作为值存入字典
        temp_dir[item['text']] = item['extend']['uuid']
        # 将图书馆的value值存入字典
        temp_dir['value'] = item['value']
        # 将单个图书馆的信息字典添加到列表中
        temp.append(temp_dir)


# # 执行的主要流程函数
# def to_go(usernumber,order_big_space_name,space_id_name,set_id,start_time,end_time,user_defind_time=None):
#
#     """
#     执行获取图书馆代号的主要流程。
#
#     :param usernumber: 用户学号
#     """
#     space_id_name = space_id_name + order_big_space_name
#
#     # 调用manage_user模块的main函数，获取编码后的密码
#     encode_pwd = manage_user.main(usernumber)
#     # 调用load模块的get_user_token函数，获取用户令牌
#     new_token = load.get_user_token(usernumber,encode_pwd)
#
#     build_set_and_id.run(new_token,order_big_space_name,space_id_name,set_id,start_time,end_time,user_defind_time)

# ... existing code ...

import time

def prepare_to_go(usernumber,order_big_space_name, space_id_name, set_id, start_time, end_time,user_defind_time=None,debug=False,password=None,interactive=True,stop_event=None):
    """
    登录并提前解析预约所需的 libId/seatId，返回可直接提交的预约上下文。
    """
    big_liberary_name, resolved_space_id_name = resolve_library_names(order_big_space_name, space_id_name)
    user_session = create_session()
    try:
        if stop_event is not None and stop_event.is_set():
            print('已停止预约')
            return 'stopped'
        encode_pwd = manage_user.main(usernumber, password=password, interactive=interactive)
        new_token = load.get_user_token(usernumber, encode_pwd, user_session)
        context = build_set_and_id.prepare_reservation_context(
            new_token,
            big_liberary_name,
            order_big_space_name,
            resolved_space_id_name,
            set_id,
            start_time,
            end_time,
            usernumber,
            session=user_session,
            user_defind_time=user_defind_time,
            debug=debug,
            stop_event=stop_event,
        )
        if context == 'stopped':
            user_session.close()
        return context
    except Exception:
        user_session.close()
        raise

def submit_to_go(prepared_context,debug=False,stop_event=None):
    if prepared_context == 'stopped':
        return 'stopped'
    try:
        with REQUEST_SEMAPHORE:
            return build_set_and_id.submit_prepared_reservation(
                prepared_context,
                debug=debug,
                stop_event=stop_event,
            )
    finally:
        session_obj = getattr(prepared_context, 'session', None)
        if session_obj is not None:
            session_obj.close()

# 执行的主要流程函数,big_liberary_name是f6，华天
def to_go(usernumber,order_big_space_name, space_id_name, set_id, start_time, end_time,user_defind_time=None,debug=False,password=None,interactive=True,stop_event=None):
    """
    执行预约流程：先预热，再等待开抢，最后只提交 saveRecord。
    """
    try:
        prepared_context = prepare_to_go(
            usernumber,
            order_big_space_name,
            space_id_name,
            set_id,
            start_time,
            end_time,
            user_defind_time=user_defind_time,
            debug=debug,
            password=password,
            interactive=interactive,
            stop_event=stop_event,
        )
        if prepared_context == 'stopped':
            return 'stopped'
        if not user_defind_time and wait_until_reservation_start(stop_event=stop_event):
            close_prepared_contexts([prepared_context])
            return 'stopped'
        return submit_to_go(prepared_context, debug=debug, stop_event=stop_event)
    except Exception as e:
        if debug:
            tb = traceback.format_exc()
            print(e)
            print(tb)
        else:
            print(f"Error: {e}")
        
# 此函数用于取消预约
def Cancel(usernumber,start_time,password=None,interactive=True):
    user_session = create_session()
    try:
        # 获取用户token
        # 调用manage_user模块的main函数，获取编码后的密码
        encode_pwd = manage_user.main(usernumber, password=password, interactive=interactive)
        # 调用load模块的get_user_token函数，获取用户令牌
        new_token = load.get_user_token(usernumber, encode_pwd,user_session)

        #取消预约板块
        cancel_record.Cancel_Setid_Run(new_token,start_time,user_session)
    finally:
        user_session.close()


def thread_cancel(*togo_args_list):
    """
    多线程执行 to_go 函数。
    :param togo_args_list: 多个 to_go 函数所需的参数元组
    """
    threads = []
    for togo_args in togo_args_list:
        # 创建线程对象，target 为 to_go 函数，args 为参数元组
        thread = threading.Thread(target=Cancel, args=togo_args)
        threads.append(thread)

        # 启动线程
        thread.start()

        # 增加小幅度随机延迟
        random_delay = random.uniform(0, 0.5)  # 随机延迟0到0.5秒
        time.sleep(random_delay)

    # 等待所有线程完成
    for thread in threads:
        thread.join()




def prepare_thread_contexts(*togo_args_list, stop_event=None):
    contexts = []
    try:
        for togo_args in togo_args_list:
            if stop_event is not None and stop_event.is_set():
                print('已停止预约')
                break
            context = prepare_to_go(*togo_args, stop_event=stop_event)
            if context == 'stopped':
                break
            contexts.append(context)
            delay = random.uniform(0, 0.15)
            if stop_event is not None:
                if stop_event.wait(delay):
                    print('已停止预约')
                    break
            else:
                time.sleep(delay)
        return contexts
    except Exception:
        close_prepared_contexts(contexts)
        raise

def thread_submit_prepared(contexts, stop_event=None):
    threads = []
    for context in contexts:
        if stop_event is not None and stop_event.is_set():
            print('已停止预约')
            break
        thread = threading.Thread(target=submit_to_go, args=(context,), kwargs={'stop_event': stop_event})
        threads.append(thread)
        thread.start()
        delay = random.uniform(0, 0.12)
        if stop_event is not None:
            if stop_event.wait(delay):
                print('已停止预约')
                break
        else:
            time.sleep(delay)

    for thread in threads:
        thread.join()

def thread_run(*togo_args_list, stop_event=None):
    """
    多线程执行预约。先完成全部预热，再等待统一开抢时间并提交。

    :param togo_args_list: 多个 to_go 函数所需的参数元组
    """
    contexts = []
    try:
        contexts = prepare_thread_contexts(*togo_args_list, stop_event=stop_event)
        if not contexts:
            return
        should_wait = all(getattr(context, 'user_defind_time', None) is None for context in contexts)
        if should_wait and wait_until_reservation_start(stop_event=stop_event):
            return
        thread_submit_prepared(contexts, stop_event=stop_event)
    finally:
        close_prepared_contexts(contexts)

# ... existing code ...
# 程序入口，当脚本作为主程序运行时执行以下代码
if __name__ == '__main__':
    i = 1

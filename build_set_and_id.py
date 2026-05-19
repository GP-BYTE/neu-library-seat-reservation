import requests
import json
from datetime import date
import os
from datetime import date, timedelta
import use_cache
import random
import time
import logging
import traceback
import re
from dataclasses import dataclass

green = '\033[92m'
red = '\033[91m'
yellow = '\033[93m'
blue = '\033[94m'
end = '\033[0m'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
CACHE_DIR = 'cache'
SPACE_CACHE_FILE = os.path.join(CACHE_DIR, 'space_id.json')
SEAT_CACHE_FILE = os.path.join(CACHE_DIR, 'lib_set.json')
SAVE_RECORD_TIMEOUT = (1.5, 5)

BUSINESS_STOP_KEYWORDS = (
    'success',
    '重合',
    '未完成',
    '已预约',
    '已被预约',
    '已被占用',
    '不可预约',
    '不存在',
    '频繁',
    '参数',
    '未找到座位映射',
)

@dataclass
class PreparedReservationContext:
    token: str
    rebuild_big_libname: str
    spacename: str
    with_number_spacename: str
    set_id: str
    start_time: str
    end_time: str
    usernumber: str
    session: object
    libid: object
    seatid: object
    user_defind_time: object = None

def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)

def seat_name_candidates(set_name):
    text = str(set_name).strip().upper()
    candidates = [text]
    match = re.match(r'^0*(\d+)([A-Z]+)$', text)
    if match:
        number, suffix = match.groups()
        candidates.append(f"{int(number)}{suffix}")
        candidates.append(f"{int(number):02d}{suffix}")
    result = []
    for candidate in candidates:
        if candidate not in result:
            result.append(candidate)
    return result

def stop_requested(stop_event):
    return stop_event is not None and stop_event.is_set()

def interruptible_sleep(seconds, stop_event=None):
    if stop_event is not None:
        return stop_event.wait(seconds)
    time.sleep(seconds)
    return False

def should_stop_after_response(msg):
    text = str(msg)
    return any(keyword in text for keyword in BUSINESS_STOP_KEYWORDS)

def warm_order_session(user_token, session):
    headers = {
        'reader_token': user_token,
        'referer': 'https://order.lib.nsu.edu.cn/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 14; V2307A Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240301 MMWEBID/4922 MicroMessenger/8.0.48.2580(0x28003052) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 Edg/131.0.0.0',
    }
    try:
        session.get(
            'https://order.lib.nsu.edu.cn/api/reader-no-filter/library/listCampus',
            headers=headers,
            timeout=(1.5, 4),
        )
    except Exception as exc:
        logging.info('预约连接预热未完成，将在正式请求时继续尝试：%s', exc)

"""
这个模块是用于建立每个座位和其id的映射关系，之后将信息保存在本地方便调用
并且提供了统一接口，方便调用，不需要关心具体的实现细节，只需要按照标准向函数传入参数即可
"""

# 获取图书馆的代号，随机放入一个学号就可以
def get_id_liberary(user_token,libserary_name,session):
    """
    根据用户令牌获取图书馆的代号信息。

    :param user_token: 用户令牌，用于验证用户身份
    :param libserary_name: 图书馆名称
    :return: 图书馆的代号
    """
    # 设置请求头，包含用户令牌、referer和user-agent信息
    headers = {
        'reader_token':user_token,
        'referer':'https://order.lib.nsu.edu.cn/',
        'user-agent':'Mozilla/5.0 (Linux; Android 14; V2307A Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240301 MMWEBID/4922 MicroMessenger/8.0.48.2580(0x28003052) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 Edg/131.0.0.0',
    }
    # 发送GET请求获取图书馆列表信息
    res = session.get('https://order.lib.nsu.edu.cn/api/reader-no-filter/library/listCampus',headers=headers).text
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
    # 打印处理后的图书馆信息列表

    for item in temp:
        # 查找指定名称的图书馆
        if libserary_name in item.keys():
            # 返回该图书馆的代号

            return item['value']


def get_now_time(user_defind = None):
    """
    获取当前日期和明天的日期，并格式化为指定的字符串。

    :return: 明天的开始时间、结束时间和日期
    """
    if user_defind is None:
        # 获取当前日期
        current_date = date.today()
        # 计算明天的日期
        next_day = current_date + timedelta(days=1)

        # 格式化为指定字符串
        start_time = f"{next_day} 08:00:00"
        end_time = f"{next_day} 22:00:00"


        return start_time, end_time, next_day
    else:
        # 通过自定义时间来获取 格式是2025-03-21
        current_date = user_defind
        start_time = f"{current_date} 08:00:00"
        end_time = f"{current_date} 22:00:00"
        return start_time, end_time, current_date


#这个函数是获取指定的例如书库阅览室自习室的详细信息,返回其的uuid
def get_all_liberary_bigger_space(user_token,aim_name_liberary_space,session):
    """
    获取指定图书馆区域的详细信息，返回其uuid。

    :param user_token: 用户令牌，用于验证用户身份
    :param aim_name_liberary_space: 目标图书馆区域的名称
    :return: 目标图书馆区域的uuid
    """
    # print(start_time,end_time)
    url = 'https://order.lib.nsu.edu.cn/api/reader-no-filter/library/listType'
    headers = {
        'reader_token': user_token,
        'user-agent': 'Mozilla/5.0 (Linux; Android 14; V2307A Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240301 MMWEBID/4922 MicroMessenger/8.0.48.2580(0x28003052) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 Edg/131.0.0.0',
    }
    # 发送GET请求获取图书馆区域信息
    res = session.get(url,headers=headers).text
    # 解析JSON数据
    res = json.loads(res)
    # 提取图书馆区域数据
    spaces = res['data']

    for item in spaces:
        # 查找指定名称的图书馆区域
        if item['name'] == aim_name_liberary_space:
            # 返回该区域的uuid
            return item['uuid']

# 这个函数是用来获取指定区域的详细座位信息（不带207 30B类似编号的）,这段函数一定要记住提交方式
# 虽然从分析来看可以使用json，但是我发现使用json提交只会返回华天图书馆信息，永远不会返回f6信息，所以这里使用的是params
def get_aim_bigger_space_details(user_token,space_uuid,rebulid_lib_name,session,user_defind_time=None):
    """
    获取指定区域的详细座位信息。

    :param user_token: 用户令牌，用于验证用户身份
    :param space_uuid: 区域的uuid
    :return: 详细座位信息
    """
    # 后期这里的名字要从外界获取，需要改进,is rebranded
    liberaryid = get_id_liberary(user_token,rebulid_lib_name,session)


    start_time,end_time,current_date = get_now_time(user_defind_time)
    url = 'https://order.lib.nsu.edu.cn/api/reader-no-filter/library/listReserve'
    headers = {
       'reader_token': user_token,
        'user-agent': 'Mozilla/5.0 (Linux; Android 14; V2307A Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240301 MMWEBID/4922 MicroMessenger/8.0.48.2580(0x28003052) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 Edg/131.0.0.0',

    }
    parms = {
        'reserveDate':str(current_date),
        'buildingsId':'',
        'campusId':liberaryid,
        'startDateTime':start_time,
       'endDateTime':end_time,
        'libTypeUuid':str(space_uuid),
        'pageNum':'1',
        'pageSize':'10',
    }

    # 发送GET请求获取座位信息
    res = session.get(url,headers=headers,params=parms).text
    # 解析JSON数据
    res = json.loads(res)

    # 返回座位信息
    return res['data']

# 通过输入'207书库阅览区'、'F6图书室'来让函数返回对应的libid,同时还存储了本地cache，方便以后快读调用
def input_spaces_return_libid(spaces_datils,aim_space_name,renew = False):
    """
    通过输入区域名称返回对应的libid，并可选择更新本地缓存。

    :param spaces_datils: 各个区域的详细信息
    :param aim_space_name: 目标区域的名称
    :param renew: 是否更新本地缓存，默认为False
    :return: 目标区域的libid
    """
    if spaces_datils is None:
        print('返回的各个区域数据为空')

    if renew:
        _ensure_cache_dir()
        if not os.path.exists(SPACE_CACHE_FILE):
            tem = []
            for item in spaces_datils:
                tem_dic = {}
                # 将区域名称和对应的libid存入字典
                tem_dic[item['libraryName']] = item['libraryId']
                tem.append(tem_dic)
            tem = json.dumps(tem)
            # 将数据写入缓存文件
            with open(SPACE_CACHE_FILE,'w') as f:
                f.write(tem)
        else:
            with open(SPACE_CACHE_FILE,'r') as f:
                tem = json.load(f)
            for item1 in spaces_datils:
                for item2 in tem:
                    if item1['libraryName'] in item2.keys():
                        continue
                    else:
                        item2[item1['libraryName']] = item1['libraryId']

            with open(SPACE_CACHE_FILE,'w') as f:
                json.dump(tem,f)


    for item in spaces_datils:
        # 查找指定名称的区域

        if item['libraryName'] == aim_space_name:
            # 返回该区域的libid

            return item['libraryId']
    else:
        print(f'未找到{spaces_datils}信息')

def get_details_sets(user_token,libid,setid,session,user_defind_time=None,renew=True):
    """
    根据座位编号获取座位的详细信息。

    :param user_token: 用户令牌，用于验证用户身份
    :param libid: 图书馆区域的id
    :param setid: 座位编号
    :return: 座位的id
    """
    # 传入日期，在后面加上00：00：00
    start_time,endtime,current_date = get_now_time(user_defind_time)

    new_current_date = f"{current_date} 00:00:00"

    url = 'https://order.lib.nsu.edu.cn/api/reader-no-filter/library/listSeatByLibId?'
    headers = {
        'reader_token': user_token,
        'user-agent': 'Mozilla/5.0 (Linux; Android 14; V2307A Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240301 MMWEBID/4922 MicroMessenger/8.0.48.2580(0x28003052) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 Edg/131.0.0.0',
    }
    parms = {
        'libId':libid,
        'reserveTime':new_current_date
    }
    # 发送GET请求获取座位详细信息
    res = session.get(url,headers=headers,params=parms)


    data = json.loads(res.text)['data']


    # 初写或复写或添加cache
    if renew:
        _ensure_cache_dir()
        if not os.path.exists(SEAT_CACHE_FILE):
            data_dic = {}
            temp = {}
            for item in data:
                # 将座位编号和对应的座位id存入字典
                temp[item['seatNo']] = item['seatId']
            data_dic[libid] = temp
            data_dic = json.dumps(data_dic)
            with open(SEAT_CACHE_FILE,'w') as f:
                # 将数据写入缓存文件
                f.write(data_dic)
        else:
            with open(SEAT_CACHE_FILE,'r') as f:
                data_dic = json.load(f)
            temp = {}
            for item in data:
                if item['seatNo'] in data_dic.keys():
                    continue
                # 将座位编号和对应的座位id存入字典
                temp[item['seatNo']] = item['seatId']
            data_dic[libid] = temp
            data_dic = json.dumps(data_dic)
            with open(SEAT_CACHE_FILE,'w') as f:
                # 将数据写入缓存文件
                f.write(data_dic)

    candidates = seat_name_candidates(setid)
    for item in data:
        # 查找指定编号的座位
        if str(item['seatNo']).strip().upper() in candidates:
            # 返回该座位的id

            return item['seatId']

# 发送预约座位请求
def order_set_response(token,libid,setid,want_starttime,want_endtime,session,user_defind_time=None):
    """
    发送预约座位请求。

    :param token: 用户令牌，用于验证用户身份
    :param libid: 图书馆区域的id
    :param setid: 座位的id
    :param want_starttime: 希望预约的开始时间
    :param want_endtime: 希望预约的结束时间
    """
    start_time,endtime,current_data = get_now_time(user_defind_time)


    want_starttime = f"{current_data} {want_starttime}"
    want_endtime = f"{current_data} {want_endtime}"
    current_data = f"{current_data} 00:00:00"


    headers = {
        'reader_token': token,
        'user-agent': 'Mozilla/5.0 (Linux; Android 14; V2307A Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240301 MMWEBID/4922 MicroMessenger/8.0.48.2580(0x28003052) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 Edg/131.0.0.0',
    }
    data = {
        'libId':libid,
        'seatId':setid,
        'reserveStartTime':want_starttime,
        'reserveEndTime':want_endtime,
        'reserveTime':current_data
    }
    # 发送POST请求进行座位预约
    res = session.post(
        'https://order.lib.nsu.edu.cn/api/reader-api/reserve/saveRecord',
        headers=headers,
        data=data,
        timeout=SAVE_RECORD_TIMEOUT,
    ).text
    return json.loads(res)

def order_set(token,libid,setid,want_starttime,want_endtime,session,user_defind_time=None):
    """
    发送预约座位请求，返回接口 msg，保持旧调用方式兼容。
    """
    res = order_set_response(token,libid,setid,want_starttime,want_endtime,session,user_defind_time)
    return res.get('msg', str(res))

# 根据translate库返回信息来判断信息应该是重新爬取还是直接使用cache，use——cache——load的意思是默认是否使用cache
def check_use_cache_or_web(user_token,with_number_spacename,detials,set_id,spacename,rebuild_big_libname,session,use_cache_load=True,user_defind_time=None):
    # 初始化lib和setid变量
    if use_cache_load:
        print(f'{green}正在使用cache访问转化信息{end}')
        # 返回图书区域id和转化后座位id
        lib,setid = use_cache.Translate(with_number_spacename, set_id)
        if setid and lib:
            return lib,setid
        print(f'{red}cache未命中{end}')
    print('正在使用web访问转化信息')

    if detials == '':

        # 调用 get_all_liberary_bigger_space 函数，根据用户令牌和图书馆区域名称获取该区域的uuid
        uuid = get_all_liberary_bigger_space(user_token, spacename,session)

        # 调用 get_aim_bigger_space_details 函数，根据用户令牌和区域uuid获取该区域的详细座位信息
        detials = get_aim_bigger_space_details(user_token, uuid, rebuild_big_libname, session,user_defind_time)

    # 调用 input_spaces_return_libid 函数，根据区域详细信息和带有编号的区域名称获取该区域的libid
    lib1 = input_spaces_return_libid(detials, with_number_spacename,renew=True)

    # 调用 get_details_sets 函数，根据用户令牌、区域libid和座位编号获取该座位的id
    setid1 = get_details_sets(user_token, lib1, set_id, session,user_defind_time, renew=True)

    return lib1,setid1

def prepare_reservation_context(token,rebuild_big_libname,spacename,with_number_spacename,set_id,start_time,end_time,usernumber,session,user_defind_time=None,use_cache_load=True,debug=False,stop_event=None):
    """
    提前完成登录后的座位映射解析和连接预热。
    返回的上下文可在开抢时直接提交 saveRecord，减少关键路径耗时。
    """
    if stop_requested(stop_event):
        logging.info('预约预热已停止')
        return 'stopped'

    detials = ''
    if not use_cache_load:
        print(f'{red}未使用cache访问转化信息{end}')
        uuid = get_all_liberary_bigger_space(token,spacename,session)
        detials = get_aim_bigger_space_details(token,uuid,rebuild_big_libname,session,user_defind_time)

    lib, seatid = check_use_cache_or_web(
        token,
        with_number_spacename,
        detials,
        set_id,
        spacename,
        rebuild_big_libname,
        session,
        use_cache_load,
        user_defind_time,
    )
    if not lib or not seatid:
        msg = f'未找到座位映射：区域={with_number_spacename}，座位={set_id}'
        logging.error(f'{red}{msg}{end}')
        raise ValueError(msg)

    if stop_requested(stop_event):
        logging.info('预约预热已停止')
        return 'stopped'

    warm_order_session(token, session)
    logging.info(
        '预热完成：用户%s，区域%s，座位%s，libId=%s，seatId=%s',
        usernumber,
        with_number_spacename,
        set_id,
        lib,
        seatid,
    )
    return PreparedReservationContext(
        token=token,
        rebuild_big_libname=rebuild_big_libname,
        spacename=spacename,
        with_number_spacename=with_number_spacename,
        set_id=set_id,
        start_time=start_time,
        end_time=end_time,
        usernumber=usernumber,
        session=session,
        libid=lib,
        seatid=seatid,
        user_defind_time=user_defind_time,
    )

def submit_prepared_reservation(context,max_attempts=20,stop_event=None,debug=False):
    """
    使用预热好的 libId/seatId 提交预约。此阶段不再访问列表/座位解析接口。
    """
    if context == 'stopped':
        return 'stopped'
    if stop_requested(stop_event):
        logging.info('预约已停止')
        return 'stopped'

    msg = 'failed'
    for attempt in range(1, max_attempts + 1):
        if stop_requested(stop_event):
            logging.info('预约已停止')
            return 'stopped'
        try:
            submit_start = time.perf_counter()
            response = order_set_response(
                context.token,
                context.libid,
                context.seatid,
                context.start_time,
                context.end_time,
                context.session,
                context.user_defind_time,
            )
            elapsed_ms = int((time.perf_counter() - submit_start) * 1000)
            msg = response.get('msg', str(response))

            if msg == 'success':
                logging.info(
                    f'{blue}用户{context.usernumber} : 已经成功预约时间：{context.start_time}-{context.end_time} 的{context.set_id} 座位，提交耗时 {elapsed_ms}ms{end}'
                )
                return msg

            if should_stop_after_response(msg):
                logging.warning(
                    f'{red}用户{context.usernumber} : 预约未继续重试，接口返回：{msg}，提交耗时 {elapsed_ms}ms{end}'
                )
                return msg

            logging.error(
                f'{red}用户{context.usernumber} : 第{attempt}次预约失败，接口返回：{msg}，提交耗时 {elapsed_ms}ms{end}'
            )
        except Exception as e:
            if debug:
                tb = traceback.format_exc()
                print(e)
                print(tb)
            else:
                logging.error(f'{red}用户{context.usernumber} : 第{attempt}次预约异常：{e}{end}')

        if attempt < max_attempts:
            if interruptible_sleep(random.uniform(0.25, 0.9), stop_event):
                logging.info('预约已停止')
                return 'stopped'
    else:
        logging.error(f'{red}用户{context.usernumber} : 达到最大尝试次数，停止预约{end}')
            
    return msg

# 统一调用的函数,'08:00:00','08:40:00'
# 输入token，书库阅览区，207书库阅览区，20701D，'08:00:00','08:40:00'
def run(token,rebuild_big_libname,spacename,with_number_spacename,set_id,start_time,end_time,usernumber,session,user_defind_time=None,use_cache_load=True,debug=False,max_attempts=20,stop_event=None):
    """
    统一调用函数，完成座位预约流程。

    :param token: 用户令牌，用于验证用户身份
    :param spacename: 图书馆区域的名称
    :param with_number_spacename: 带有编号的图书馆区域名称
    :param set_id: 座位编号
    :param start_time: 希望预约的开始时间
    :param end_time: 希望预约的结束时间
    F6图书馆区域请选择书库阅览区！
    """

    try:
        context = prepare_reservation_context(
            token,
            rebuild_big_libname,
            spacename,
            with_number_spacename,
            set_id,
            start_time,
            end_time,
            usernumber,
            session,
            user_defind_time=user_defind_time,
            use_cache_load=use_cache_load,
            debug=debug,
            stop_event=stop_event,
        )
    except ValueError as exc:
        return str(exc)
    return submit_prepared_reservation(context,max_attempts=max_attempts,stop_event=stop_event,debug=debug)


if __name__ == '__main__':
    print('请通过 run_order.py 或 gradio_app.py 启动预约流程。')

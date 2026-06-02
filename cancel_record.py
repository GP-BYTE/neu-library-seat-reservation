# 导入 requests 库，用于发送 HTTP 请求
import requests
# 导入 json 库，用于处理 JSON 数据
import json
from session_set import create_session

green = '\033[92m'
red = '\033[91m'
yellow = '\033[93m'
blue = '\033[94m'
end = '\033[0m'

def get_record_list(user_token,session):
    """
    获取用户的预约记录列表。

    :param user_token: 用户的身份验证 token
    :return: 包含预约记录信息的列表
    """
    # 定义请求的 URL
    url = 'https://order.lib.nsu.edu.cn/api/reader-api/reserve/recordList'
    # 定义请求头，包含用户代理和读者 token
    headers = {
        'user-agent':'Mozilla/5.0 (Linux; Android 14; V2307A Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240301 MMWEBID/4922 MicroMessenger/8.0.48.2580(0x28003052) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 Edg/131.0.0.0',
        'reader_token':user_token,
    }
    # 定义请求的 JSON 数据
    jsons = {
        'pageNum':'1',
        'pageSize':'10',
        'startTime':None,
        'endTime':None,
    }
    # 发送 POST 请求并获取响应文本
    response = session.post(url,headers=headers,json=jsons)
    try:
        res = response.json()
    except ValueError as exc:
        raise ValueError('预约记录接口返回异常，无法解析响应') from exc
    if not isinstance(res, dict):
        raise ValueError('预约记录接口返回格式异常')
    msg = res.get('msg')
    # 提取数据列表。平台不同版本可能返回 dataList，也可能返回 data。
    data = res.get('dataList')
    if data is None:
        data = res.get('data')
    has_empty_data_container = isinstance(data, dict) and not data
    if isinstance(data, dict):
        data = data.get('dataList') or data.get('list') or data.get('records') or []
    if (data is None or has_empty_data_container) and msg not in (None, 'success'):
        raise ValueError(f"预约记录查询失败：{msg}")
    if data is None:
        data = []
    if not isinstance(data, list):
        raise ValueError('预约记录接口返回列表格式异常')
    # 初始化一个空列表，用于存储处理后的预约记录
    tem_dic = []
    # 遍历数据列表
    for item in data:
        if not isinstance(item, dict):
            continue
        # 初始化一个空字典，用于存储单个预约记录的信息
        tem_list = {}
        # 提取预约记录的 ID
        tem_list['id'] = item.get('id', '')
        # 提取预约记录的开始时间
        tem_list['startTime'] = item.get('startTime', '')
        # 提取预约记录的结束时间
        tem_list['endTime'] = item.get('endTime', '')
        # 提取预约记录的状态名称
        tem_list['statusName'] = item.get('statusName', '')
        # 提取预约记录的座位号
        tem_list['seatNum'] = item.get('seatNum', '')
        # 将单个预约记录添加到列表中
        tem_dic.append(tem_list)
    # 返回处理后的预约记录列表
    return tem_dic

# 这段代码通过输入一个包含了指定信息的预约信息的列表，以及一个指定的开始时间来找到指定的预约信息的ID。时间格式为'2025-03-23 09:20:00'
def get_cancel_aim_id(tem_dic,start_time):
    """
    根据指定的开始时间和预约状态，从预约记录列表中找到要取消的预约记录的 ID。

    :param tem_dic: 包含预约记录信息的列表
    :param start_time: 指定的开始时间，格式为 'YYYY-MM-DD HH:MM:SS'
    :return: 要取消的预约记录的 ID，如果未找到则返回 None
    """
    # 遍历预约记录列表
    for item in tem_dic:
        # 检查预约状态是否为 '已约' 且开始时间是否匹配
        if item['statusName'] == '已约' and item['startTime'] == start_time:
            # 如果匹配，返回该预约记录的 ID
            return item['id']
        # 不匹配则继续下一个循环
        else:
            continue

def Cancel_Site(token,id,session):
    """
    取消指定 ID 的预约座位。

    :param token: 用户的身份验证 token
    :param id: 要取消的预约记录的 ID
    :return: 如果取消成功返回 True，否则返回 False
    """
    # 定义取消预约的 URL
    url = 'https://order.lib.nsu.edu.cn/api/reader-api/reserve/cancelBooking'
    # 定义请求头，包含用户代理和读者 token
    headers = {
        'user-agent': 'Mozilla/5.0 (Linux; Android 14; V2307A Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240301 MMWEBID/4922 MicroMessenger/8.0.48.2580(0x28003052) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 Edg/131.0.0.0',
        'reader_token': token,
    }
    # 定义请求的 JSON 数据，包含要取消的预约记录的 ID
    jsons = {
        'recordId':id,
    }
    # 发送 POST 请求并获取响应文本
    response = session.post(url,headers=headers,data=jsons)
    try:
        res = response.json()
    except ValueError as exc:
        raise ValueError('取消预约接口返回异常，无法解析响应') from exc
    if not isinstance(res, dict):
        raise ValueError('取消预约接口返回格式异常')
    # 检查响应消息是否为 'success'
    if res.get('msg') == 'success':
        # 如果成功，打印取消成功的消息并返回 True
        print(f'{green}已经成功取消座位ID为{id}的预约{end}')
        return True
    # 否则返回 False
    else:
        return False

def Cancel_Setid_Run(token,start_time,session):
    """
    根据指定的开始时间取消预约座位。

    :param token: 用户的身份验证 token
    :param start_time: 指定的开始时间，格式为 'YYYY-MM-DD HH:MM:SS'
    :return: 如果取消成功返回 True，否则返回 False
    """
    # 获取用户的预约记录列表
    tem_dic = get_record_list(token,session)
    # 找到要取消的预约记录的 ID
    cancel_id = get_cancel_aim_id(tem_dic,start_time)
    if not cancel_id:
        raise ValueError(f'未找到开始时间为 {start_time} 的已约记录')
    # 取消指定 ID 的预约座位
    status = Cancel_Site(token,cancel_id,session)
    # 返回取消结果
    return status

if __name__ == '__main__':
    token = input('请输入 reader_token：').strip()
    start_time = input('请输入取消预约开始时间（YYYY-MM-DD HH:MM:SS）：').strip()
    user_session = create_session()
    try:
        print(Cancel_Setid_Run(token, start_time, user_session))
    finally:
        user_session.close()

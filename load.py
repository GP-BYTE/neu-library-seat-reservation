from requests import Session
import pwd_encode
import json
import requests
import os


def get_user_token(user_number,encode_password,session):
    if not encode_password:
        raise ValueError(f'{user_number} 缺少密码，请先提供或缓存该账号密码')

    # 构建 multipart/form-data 参数
    data = {
        'platformCode': '00001102',
        'appCode': '00001002',
        'stunum': str(user_number),
        'password': encode_password,
        'time': '-1',
        'openId': 'null',
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 14; V2307A Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160117 MMWEBSDK/20240301 MMWEBID/4922 MicroMessenger/8.0.48.2580(0x28003052) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 Edg/131.0.0.0',
        'Referer': 'https://sso.lib.nsu.edu.cn/?appCode=00001002&platformCode=00001102&openId=null',
        'Origin': 'https://sso.lib.nsu.edu.cn',
    }
    bootstrap_token = os.environ.get('NSU_BOOTSTRAP_READER_TOKEN')
    if bootstrap_token:
        headers['reader_token'] = bootstrap_token

    # for key, value in data.items():
    #     print(f"{key}: {value}")
    send_file = {key: (None, str(value)) for key, value in data.items()}

    # 首次 GET 请求（获取必要 Cookie 或 Token）
    first_get = session.get(
        'https://sso.lib.nsu.edu.cn/api/oauth/wx/config?url=config',
        headers=headers
    )
    # print("首次响应:", first_get.text)


    # 发送 multipart/form-data 请求
    res = session.post(
        'https://sso.lib.nsu.edu.cn/api/login/readerLogin',
        headers=headers,
        files=send_file,  # 构建表单字段
    )
    if res is None:
        raise ValueError(f'{user_number} 登录请求失败')
    try:
        payload = res.json()
    except ValueError as exc:
        raise ValueError(f'{user_number} 登录接口返回异常，无法解析响应') from exc

    if not isinstance(payload, dict):
        raise ValueError(f'{user_number} 登录接口返回格式异常')

    data = payload.get('data')
    sys_reader = data.get('sysReader') if isinstance(data, dict) else None
    new_token = sys_reader.get('readerToken') if isinstance(sys_reader, dict) else None
    if not new_token:
        msg = payload.get('msg') or payload.get('message') or '请检查账号或密码'
        raise ValueError(f'{user_number} 登录失败：{msg}')
    # print("登录结果:", res)
    return new_token

if __name__ == '__main__':
    user_number = input('请输入学号：').strip()
    password = input('请输入密码：')
    encode = pwd_encode.mian_code(password)
    with Session() as user_session:
        print(get_user_token(user_number, encode, user_session))

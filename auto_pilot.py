import load
import manage_user
import session_set
import requests
import json
import re


def get_now_order(token):
    url = 'https://order.lib.nsu.edu.cn/api/reader-api/reserve/recordNew'
    headers = {
        'reader_token': token,
    }
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return None


def build_suit_to_go(usernumber,start_time,set_name,libraryName):
    spacename = ''.join(re.findall(r'[一-龥〇]', libraryName))
    print(spacename)


# ororigin_back_time是用于告诉程序用户多久回来，也就是从多久开始检测用户是否签到
def single_user_pilot(usernumber,origin_back_time):

    # 创建一个新的Session对象
    user_session = session_set.create_session()
    # 调用manage_user模块的main函数，获取编码后的密码
    encode_pwd = manage_user.main(usernumber)
    # 调用load模块的get_user_token函数，获取用户令牌
    new_token = load.get_user_token(usernumber, encode_pwd, user_session)
    # 调用get_now_order函数，获取当前订单
    now_order = get_now_order(new_token)
    # 打印当前订单
    informations = json.loads(str(now_order))
    start_time = informations['data']["startTime"]
    set_name = informations['data']["seatNum"]
    libraryName = informations['data']["libraryName"]
    build_suit_to_go(usernumber,start_time,set_name,libraryName)

if __name__ == '__main__':
    user_number = input('请输入学号：').strip()
    back_time = input('请输入预计返回时间：').strip()
    single_user_pilot(user_number, back_time)

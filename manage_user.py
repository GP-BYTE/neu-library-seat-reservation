# 导入json模块，用于处理JSON数据
import json
# 导入os模块，用于与操作系统进行交互，如文件操作
import os
# 导入自定义的pwd_encode模块，用于密码编码
import pwd_encode

USER_INFO_FILE = 'user_info.json'

def _load_user_info():
    if not os.path.exists(USER_INFO_FILE):
        return []
    try:
        with open(USER_INFO_FILE, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, list):
        return data
    return []

def _save_user_info(info):
    temp_path = f'{USER_INFO_FILE}.tmp'
    with open(temp_path, 'w') as f:
        json.dump(info, f)
    try:
        os.chmod(temp_path, 0o600)
    except OSError:
        pass
    os.replace(temp_path, USER_INFO_FILE)

# 函数功能：将用户编号和密码写入临时字典，并对密码进行编码
# 参数：user_number - 用户编号；pwd - 用户密码
# 返回值：包含用户编号和编码后密码的临时字典
def write_in_user_info(user_number,pwd):
    # 创建一个空字典，用于存储用户信息
    temp = {}
    # 调用pwd_encode模块的mian_code函数对密码进行编码
    encode = pwd_encode.mian_code(pwd)
    # 将用户编号作为键，编码后的密码作为值，存入临时字典
    temp[user_number] = encode
    return temp

# 函数功能：检查目标用户是否为新用户
# 参数：all_info - 所有用户信息列表；aim_user_number - 目标用户编号
# 返回值：如果是新用户返回True，否则返回False
def check_is_new_user(all_info,aim_user_number):
    # 遍历所有用户信息
    for i in all_info:
        # 检查目标用户编号是否在当前用户信息的键中
        if aim_user_number in i.keys():
            return False
    return True

# 函数功能：根据用户编号输出对应的用户信息
# 参数：info - 所有用户信息列表；want_user_number - 想要查询的用户编号
# 返回值：如果找到对应用户编号，返回其密码；否则返回None
def output_user_info(info,want_user_number):
    # 遍历所有用户信息
    for item in info:
        # 检查想要查询的用户编号是否在当前用户信息的键中
        if want_user_number in item.keys():
            return item[want_user_number]

def has_user(want_usernumber):
    return not check_is_new_user(_load_user_info(), want_usernumber)

def list_users():
    users = []
    for item in _load_user_info():
        if not isinstance(item, dict):
            continue
        for usernumber in item.keys():
            if usernumber not in users:
                users.append(usernumber)
    return users

def delete_user(want_usernumber):
    info = _load_user_info()
    new_info = []
    deleted = False
    for item in info:
        if not isinstance(item, dict):
            continue
        filtered = {key: value for key, value in item.items() if key != want_usernumber}
        if len(filtered) != len(item):
            deleted = True
        if filtered:
            new_info.append(filtered)
    _save_user_info(new_info)
    detect_null_delete()
    return deleted

def clear_users():
    removed = False
    if os.path.exists(USER_INFO_FILE):
        os.remove(USER_INFO_FILE)
        removed = True
    temp_path = f'{USER_INFO_FILE}.tmp'
    if os.path.exists(temp_path):
        os.remove(temp_path)
        removed = True
    return removed

# 函数功能：检测用户信息文件是否为空，如果为空则删除该文件
def detect_null_delete():
    temp = _load_user_info()
    if temp == [] and os.path.exists(USER_INFO_FILE):
        os.remove(USER_INFO_FILE)

# 函数功能：主函数，处理用户信息的写入和查询
# 参数：want_usernumber - 想要操作的用户编号
def main(want_usernumber, password=None, interactive=True):
    temp = _load_user_info()
    if check_is_new_user(temp,want_usernumber):
        if password is None:
            if not interactive:
                raise ValueError(f'{want_usernumber} 未缓存密码，请先提供密码')
            print(f'{want_usernumber}请输入你的密码')
            information = input('请在此输入：')
        else:
            information = password
        new_info = write_in_user_info(want_usernumber,information)
        temp.append(new_info)
        _save_user_info(temp)
        print('写入成功')
    elif password is not None:
        encoded_password = pwd_encode.mian_code(password)
        for item in temp:
            if want_usernumber in item:
                item[want_usernumber] = encoded_password
                break
        _save_user_info(temp)
        print('更新成功')

    pwd = output_user_info(temp,want_usernumber)
    return pwd

# 程序入口，当脚本作为主程序运行时执行以下代码
if __name__ == '__main__':
    user_number = input('请输入学号：').strip()
    main(user_number)

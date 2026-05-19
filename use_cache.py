# 导入os模块，用于操作系统相关功能，这里虽导入但未使用
import os
# 导入json模块，用于处理JSON数据
import json
import threading
import logging
import re

# 创建一个线程锁
lock = threading.Lock()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SPACE_CACHE_FILE = 'cache/space_id.json'
SEAT_CACHE_FILE = 'cache/lib_set.json'

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

def _load_json_cache(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        logging.warning("缓存文件不可用，将重新从网络获取: %s", path)
        return None

def translate_libid(lib_name):
    """
    将书库名称转换为书库ID。

    :param lib_name: 书库的名称
    :return: 如果找到对应的书库ID，则返回该ID；否则返回False
    """
    lib_info = _load_json_cache(SPACE_CACHE_FILE)
    if not isinstance(lib_info, list):
        return False
    for i in lib_info:
        if isinstance(i, dict) and lib_name in i.keys():
            return i[lib_name]
    # 如果未找到，返回False
    return False

def translate_setsid(libid,set_name):
    """
    将书库ID和集合名称转换为集合ID。

    :param libid: 书库的ID
    :param set_name: 集合的名称
    :return: 如果找到对应的集合ID，则返回该ID；否则返回False
    """
    set_info = _load_json_cache(SEAT_CACHE_FILE)
    if not isinstance(set_info, dict):
        return False
    # 遍历set_info中的每个键值对
    for name_idx,lists in set_info.items():
        # 检查当前键是否与书库ID不匹配
        if str(name_idx) != str(libid):
            # 如果不匹配，跳过当前循环
            continue
        else:
            # 遍历当前书库ID对应的集合信息
            candidates = seat_name_candidates(set_name)
            for name,id in lists.items():
                # 检查当前集合名称是否与目标集合名称匹配
                if str(name).strip().upper() in candidates:
                    # 如果匹配，返回对应的集合ID
                    return id
    # 如果未找到，返回False
    return False

def Translate(lib_name,set_name):
    """
    将书库名称和集合名称转换为集合ID。

    :param lib_name: 书库的名称
    :param set_name: 集合的名称
    :return: 如果找到对应的集合ID，则返回该ID；否则返回False
    """
    # 获取锁
    lock.acquire()
    logging.info(f"正在翻译 {lib_name} 和 {set_name}")
    try:
        if lib_name is None:
            return False , False
        # 调用translate_libid函数获取书库ID
        libid = translate_libid(lib_name)
        # 调用translate_setsid函数获取集合ID
        setid = translate_setsid(libid,set_name)
        # 返回集合ID
        return libid,setid
    finally:
        logging.info(f"翻译完成 {lib_name} 和 {set_name}")
        # 释放锁
        lock.release()


if __name__ == '__main__':
    lib_name = input('请输入区域名称：').strip()
    seat_name = input('请输入座位号：').strip()
    print(Translate(lib_name, seat_name))

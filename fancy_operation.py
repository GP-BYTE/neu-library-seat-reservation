# 导入 build_set_and_id 模块，可能用于构建集合和 ID
import build_set_and_id
# 导入 json 模块，用于处理 JSON 数据
import json
# 导入 time 模块，用于处理时间相关操作
import time
# 导入 main 模块，可能包含主要的业务逻辑
import main
# 导入 threading 模块，用于实现多线程操作
import threading
import cancel_record
"""
这里的函数是用于一些花活的，比如将一个整的时间段拆分为一个小的时间段来预约，这样就不用担心预约签到问题
而且可以将两个座位以20分钟为单位交叉预约可以一个人占用两个座位（不推荐容易上校墙被喷）
"""

def split_time(start_time, end_time, interval):
    """
    将一个时间段拆分为多个小时间段。
    :param start_time: 时间段的开始时间，格式为 'HH:MM:SS'
    :param end_time: 时间段的结束时间，格式为 'HH:MM:SS'
    :param interval: 小时间段的间隔，单位为分钟
    :return: 包含小时间段的列表
    """
    # 将时间字符串转换为时间对象
    start_time = time.strptime(start_time, '%H:%M:%S')
    end_time = time.strptime(end_time, '%H:%M:%S')
    # 计算小时间段的数量
    num_intervals = int((time.mktime(end_time) - time.mktime(start_time)) / (interval * 60))
    # 初始化小时间段的列表
    intervals = []
    # 生成小时间段
    for i in range(num_intervals):
        # 计算小时间段的开始时间
        start = time.strftime('%H:%M:%S', time.localtime(time.mktime(start_time) + i * interval * 60))
        # 计算小时间段的结束时间
        end = time.strftime('%H:%M:%S', time.localtime(time.mktime(start_time) + (i + 1) * interval * 60))
        # 将小时间段添加到列表中
        intervals.append((start, end))
    # 返回小时间段的列表
    return intervals

def splits_run(usernumber, order_big_space_name, space_id_name, set_id, start_time, end_time, interval, user_defind_time=None, debug=False):
    """
    对拆分后的时间段使用多线程进行预约操作。
    :param usernumber: 用户编号
    :param order_big_space_name: 预约的大空间名称
    :param space_id_name: 空间 ID 名称
    :param set_id: 座位 ID
    :param start_time: 时间段的开始时间，格式为 'HH:MM:SS'
    :param end_time: 时间段的结束时间，格式为 'HH:MM:SS'
    :param interval: 小时间段的间隔，单位为分钟
    :param user_defind_time: 用户自定义时间，默认为 None
    :param debug: 是否开启调试模式，默认为 False
    """
    # 调用 split_time 函数将大时间段拆分为多个小时间段
    times_list = split_time(start_time, end_time, interval)

    # 初始化线程列表
    threads = []
    # 遍历拆分后的小时间段列表
    for time in times_list:
        # 创建一个线程，目标函数为 main.to_go，传入相应的参数
        thread = threading.Thread(target=main.to_go, args=(usernumber, order_big_space_name, space_id_name, set_id, time[0], time[1], user_defind_time, debug))
        # 将线程添加到线程列表中
        threads.append(thread)
        # 启动线程
        thread.start()

    # 等待所有线程执行完毕
    for thread in threads:
        thread.join()

def cancel_splits_run(usernumber,date,start_time, end_time,interval):
    """
    对拆分后的时间段使用多线程进行取消操作。
    :param usernumber: 用户编号
    :param start_time: 时间段的开始时间，格式为 'HH:MM:SS'
    :param interval: 小时间段的间隔，单位为分钟
    :param end_time: 时间段的结束时间，格式为 'HH:MM:SS'
    """
    # 调用 split_time 函数将大时间段拆分为多个小时间段
    times_list = split_time(start_time, end_time, interval)
    # 初始化线程列表
    threads = []
    # 遍历拆分后的小时间段列表
    for time in times_list:
        new_time = date + ' ' + time[0]
        # 创建一个线程，目标函数为 cancel_record.Cancel_Setid_Run，传入相应的参数
        thread = threading.Thread(target=main.Cancel, args=(usernumber, new_time))
        # 将线程添加到线程列表中
        threads.append(thread)
        # 启动线程
        thread.start()
    # 等待所有线程执行完毕
    for thread in threads:
        thread.join()



if __name__ == '__main__':
    # 调用 split_time 函数，将时间段拆分为20分钟的小时间段
    intervals = split_time('09:20:00', '12:20:00', 20)
    # 打印小时间段的列表
    print(intervals)
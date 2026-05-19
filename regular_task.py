import main
import json
import os
import re
import run_order

def write_schedule_to_file():
    if not os.path.exists('schedule.json'):
        with open('schedule.json', 'w') as file:
            json.dump({}, file)
    with open('schedule.json', 'r') as file:
        schedule = json.load(file)
    print("请依次输入 学号、预约开始时间、预约结束时间，用空格分隔，-1结束，默认排序从周一到周日")
    week_list = build_week_list()
    for i in range(len(week_list)):
        temporary_dic = {}
        order_info = input(f"请输入{week_list[i]}的符合格式的预约信息：")
        if order_info == '-1':
            print("输入结束。")
            break
        # 处理输入: 去除多余空格并分割为列表
        user_input = re.sub(r'\s+', ' ', order_info)  # 将多个空格替换为单个空格
        user_input = user_input.strip()  # 去除首尾空格
        user_input = user_input.split(' ')  # 按空格分割

        # 验证输入项数量是否为4
        if len(user_input) != 4:
            print("输入格式错误，请重新输入。")
            print(f'你输入的内容是{user_input}。')
            continue
            
        # 解构输入项
        usernumber, order_big_space_name, start_time, end_time = user_input
        
        # 获取区域信息
        aim_region,region = run_order.splite_aim_string(order_big_space_name)
        
        # 验证学号格式: 6位数字
        if not re.match(r'^\d{11}$', usernumber):
            print("学号格式错误，请重新输入。")
            continue
            
            
        # 验证开始时间格式: HH:MM:SS
        if not re.match(r'^\d{2}:\d{2}:\d{2}$', start_time):
            print("开始时间格式错误，请重新输入。")
            continue
            
        # 验证结束时间格式: HH:MM:SS
        if not re.match(r'^\d{2}:\d{2}:\d{2}$', end_time):
            print("结束时间格式错误，请重新输入。")
            continue

        # 将参数加入（）
        temporary_dic[usernumber] = (usernumber , aim_region, region, order_big_space_name, start_time, end_time)
        schedule[week_list[i]] = temporary_dic
    with open('schedule.json', 'w') as file:
        json.dump(schedule, file, indent=4)



def build_week_list():
    week_list = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    return week_list

if __name__ == '__main__':
    write_schedule_to_file()

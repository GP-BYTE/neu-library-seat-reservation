import re
import main


def splite_aim_string(order_string):
    translate_dic = {'216':'书库阅览区','207':'书库阅览区','307':'书库阅览区',"311":'书库阅览区','313':'书库阅览区','316':'书库阅览区','211':'学习阅览区','213':'学习阅览区'}
    try:
        region = order_string[0:3]
        aim_region = translate_dic[region]
    except KeyError:
        aim_region = '书库阅览区'
        region = ""
    return aim_region,region



def bulid_order_requests():
    """
    构建座位预约请求，处理用户输入并进行验证
    
    返回格式: (usernumber, aim_region, region, order_big_space_name, start_time, end_time)
    - usernumber: 6位数字学号
    - aim_region: 目标区域名称(书库阅览区/学习阅览区)
    - region: 原始区域编号(如216)
    - order_big_space_name: 完整座位号(如21624B)
    - start_time: 预约开始时间(HH:MM:SS格式)
    - end_time: 预约结束时间(HH:MM:SS格式)
    """

    threadL = []
    while True:
        # 提示用户输入并获取输入内容
        print("请依次输入 学号、想要预约的座位号、预约开始时间、预约结束时间，用空格分隔(最小单位20min)，-1结束")
        user_input = input()
        # 检查是否输入了-1来结束
        if user_input == '-1':
            print("输入结束。")
            main.thread_run(*threadL)
            print(threadL)
            break
        
        # 处理输入: 去除多余空格并分割为列表
        user_input = re.sub(r'\s+', ' ', user_input)  # 将多个空格替换为单个空格
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
        aim_region,region = splite_aim_string(order_big_space_name)
        
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
        threadL.append((usernumber, aim_region, region, order_big_space_name, start_time, end_time))

def build_cancel_requests():
    """
    构建座位取消请求，处理用户输入并进行验证

    返回格式: (usernumber, start_time)
    - usernumber: 6位数字学号
    - start_time: 预约开始时间(HH:MM:SS格式)
    """
    threadL = []
    while True:
        # 提示用户输入并获取输入内容
        print("请依次输入 学号、想要取消的预约开始时间，用空格分隔，-1结束")
        user_input = input()
        # 检查是否输入了-1来结束
        if user_input == '-1':
            print("输入结束。")
            main.thread_cancel(*threadL)
            print(threadL)
            break
        # 处理输入: 去除多余空格并分割为列表
        user_input = re.sub(r'\s+', ' ', user_input)  # 将多个空格替换为单个空格
        user_input = user_input.strip()  # 去除首尾空格
        user_input = user_input.split(' ')  # 按空格分割
        # 验证输入项数量是否为2
        if len(user_input) != 3:
            print("输入格式错误，请重新输入。")
            print(f'你输入的内容是{user_input}。')
            continue
        # 解构输入项
        usernumber, big_time, small_time = user_input
        # 验证学号格式: 11位数字
        if not re.match(r'^\d{11}$', usernumber):
            print("学号格式错误，请重新输入。")
            continue
        # 验证年月日时间格式: YY:MM:DD HH:MM:SS
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', big_time):
            print("年月日时间格式错误，请重新输入。")
            continue
        # 验证时分秒时间格式: HH:MM:SS
        if not re.match(r'^\d{2}:\d{2}:\d{2}$', small_time):
            print("时分秒时间格式错误，请重新输入。")
            continue
        # 组合日期和时间
        start_time = f"{big_time} {small_time}"
        # 将参数加入（）
        threadL.append((usernumber, start_time))   



def run_code():
    """
    主函数，用于运行预约代码
    """
    print("请选择功能：\n1. 预约座位\n2. 取消预约")
    choice = input("输入数字选择功能：")
    if choice == '1':
        bulid_order_requests()
    elif choice == '2':
        build_cancel_requests()
    else:
        print("无效选择，请重新输入。")
        run_code()

if __name__ == '__main__':
    run_code()

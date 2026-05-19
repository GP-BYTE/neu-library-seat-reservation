import datetime
import pytz

# 设置北京时区
beijing_tz = pytz.timezone('Asia/Shanghai')

# 获取当前系统时间
def get_system_time():
    now = datetime.datetime.now(tz=beijing_tz)
    return now.strftime('%Y-%m-%d %H:%M:%S %Z%z')

if __name__ == '__main__':
    current_time = get_system_time()
    print(f"当前系统时间：{current_time}")
    
    user_input = input("请确认当前时间是否为准确北京时间 (输入yes继续)：")
    
    if user_input.strip().lower() == 'yes':
        print("时间校验通过，程序退出~")
    else:
        print("请手动校正系统时间后再运行预约程序。")
        print("macOS 可在系统设置中开启自动设置日期与时间。")

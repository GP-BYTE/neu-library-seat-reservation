import json
import datetime

"""
这里的代码是用于构建以周为单位的每一天的预约时间表，以方便用户将程序部署到服务器上自动化运行，
通过这个代码中以标准构建的时间表运行程序，就可以实现每天的自动预约。部署前请先确认服务器的时间与北京时间一致。
不然的话会出现预约失败的情况。
"""
def write_schedule(usernumber):
    # 获取当前日期
    today = datetime.datetime.today()
    # 获取今天是星期几，0 表示星期一，6 表示星期日
    weekday = today.weekday()
    # 定义星期几的中文列表
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    # 输出今天是星期几
    print(weekday)
    print(f"今天是 {weekdays[weekday]}")

if __name__ == '__main__':
    user_number = input('请输入学号：').strip()
    write_schedule(user_number)

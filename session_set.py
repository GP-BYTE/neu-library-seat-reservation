from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests import Session
import logging
import socket
import platform

# 配置日志系统
# level=logging.INFO 设置日志级别为INFO，只记录重要信息
# format定义日志格式：时间 - 级别 - 消息
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# # 在文件顶部添加以下配置
# MAX_POOL_CONNECTIONS = 10  # 每个session的最大连接数
# MAX_RETRIES = 3  # 最大重试次数
# TIMEOUT = 5  # 超时时间(秒)

def create_session(max_pool_connections=6, max_retries=3, timeout=(3.05, 10)):
    """
    创建优化后的session连接池
    
    参数:
        max_pool_connections: 连接池最大连接数，默认4
        max_retries: GET 请求最大重试次数，默认3
        timeout: 默认请求超时时间，支持秒数或 (连接超时, 读取超时)
    
    返回:
        配置好的Session对象
    """
    session = Session()
    
    # 启用TCP Keep-Alive机制
    # 保持长连接，避免频繁建立新连接的开销
    session.keep_alive = True
    
    # 创建HTTP适配器并配置连接池
    adapter = HTTPAdapter(
        # 连接池配置
        pool_connections=max_pool_connections,  # 每个主机的最大连接数
        pool_maxsize=max_pool_connections,      # 连接池最大连接数
        
        # 重试策略配置
        max_retries=Retry(
            total=max_retries,                  # 最大重试次数
            backoff_factor=2,                 # 指数退避因子
            status_forcelist=[500, 502, 503, 504],  # 需要重试的HTTP状态码
            allowed_methods=["GET"],    # POST 由业务层判断是否重试，避免重复提交预约
            respect_retry_after_header=True,    # 遵守服务器的Retry-After头
            backoff_jitter=0.5                 # 重试间隔随机因子
        ),
        pool_block=True,  # 启用阻塞模式，避免连接泄漏
    )
    
    # 连接池超时配置
    adapter.poolmanager.connection_pool_kw['timeout'] = 30  # 连接超时30秒
    adapter.poolmanager.connection_pool_kw['block'] = True   # 启用阻塞模式，避免连接泄漏
    adapter.poolmanager.connection_pool_kw['maxsize'] = max_pool_connections  # 最大连接数
    adapter.poolmanager.connection_pool_kw['retries'] = max_retries  # 最大重试次数

    # 配置TCP Keep-Alive参数
    # 平台兼容性处理 - Linux系统支持更细粒度的Keep-Alive配置
    if platform.system() == 'Linux':
        adapter.poolmanager.connection_pool_kw['socket_options'] = [
            (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),  # 启用Keep-Alive
            (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 30),  # 探测间隔30秒
            (socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)    # 空闲60秒后开始探测
        ]
    else:  # MacOS/Windows等其他系统
        adapter.poolmanager.connection_pool_kw['socket_options'] = [
            (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),  # 仅启用Keep-Alive
        ]
    
    # 为http和https都添加适配器
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    original_request = session.request

    def request_with_timeout(method, url, **kwargs):
        kwargs.setdefault('timeout', timeout)
        return original_request(method, url, **kwargs)

    session.request = request_with_timeout

    # 安全关闭方法 - 确保所有适配器资源被正确释放
    def safe_close():
        """
        安全关闭session的方法
        1. 检查是否存在适配器
        2. 遍历所有适配器并调用其close方法
        3. 静默处理所有异常，确保程序不会因关闭失败而中断
        """
        try:
            if session.adapters:
                for adapter in session.adapters.values():
                    if hasattr(adapter, 'close'):
                        adapter.close()
        except Exception:
            pass  # 静默处理异常，确保程序健壮性
    
    # 替换默认的close方法
    session.close = safe_close
    
    return session

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64

# 将 words 数组转换为字节对象
def words_to_bytes(words):
    byte_list = []
    for word in words:
        # 将 32 位整数转换为 4 个字节
        for i in range(3, -1, -1):
            byte_list.append((word >> (i * 8)) & 0xff)
    return bytes(byte_list)

def mian_code(code):
    # 定义 key 和 iv 的 words 数组
    key_words = [825373492, 892745528, 825373492, 892745528]
    iv_words = [808464432, 808464432, 808464432, 808464432]

    # 转换为字节对象
    key = words_to_bytes(key_words)
    iv = words_to_bytes(iv_words)

    # 要加密的明文
    plaintext = f"{code}".encode('utf-8')

    # 创建 AES 加密器
    cipher = AES.new(key, AES.MODE_CBC, iv)

    # 填充明文以满足 AES 块大小要求
    padded_plaintext = pad(plaintext, AES.block_size)

    # 加密操作
    ciphertext = cipher.encrypt(padded_plaintext)

    # 将加密结果转换为 Base64 编码
    base64_ciphertext = base64.b64encode(ciphertext).decode('utf-8')

    # print("加密后的密文（Base64 编码）:", base64_ciphertext)
    return base64_ciphertext


def decode(code):
    # 定义 key 和 iv 的 words 数组
    key_words = [825373492, 892745528, 825373492, 892745528]
    iv_words = [808464432, 808464432, 808464432, 808464432]
    # 转换为字节对象
    key = words_to_bytes(key_words)
    iv = words_to_bytes(iv_words)
    # 要解密的 Base64 编码密文
    base64_ciphertext = code
    # 将 Base64 编码的密文解码为字节对象
    ciphertext = base64.b64decode(base64_ciphertext)
    # 创建 AES 解密器
    cipher = AES.new(key, AES.MODE_CBC, iv)
    # 解密操作
    decrypted_plaintext = cipher.decrypt(ciphertext)
    # 去除填充
    unpadded_plaintext = unpad(decrypted_plaintext, AES.block_size)
    # 解码为字符串
    plaintext = unpadded_plaintext.decode('utf-8')
    # print("解密后的明文:", plaintext)
    return plaintext

if __name__ == '__main__':
    password = input('请输入要编码的密码：')
    encode = mian_code(password)
    decodes = decode(encode)
    print('编码结果：', encode)
    print('解码校验：', decodes)

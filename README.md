# 图书馆座位预约工具

一个用于成都东软学院图书馆座位预约的 Python 工具，支持命令行和 Gradio 可视化界面两种使用方式。项目会在本地保存账号凭据和座位映射缓存，方便后续快速预约；开源仓库不会包含真实账号、密码、预约历史或 token。

> 请合理使用本工具，不要高频请求、恶意抢占或影响图书馆预约系统正常运行。

## 最近更新

- 多账号预约改为账号级独立登录，每个账号使用自己的密码缓存或本次填写的密码，不复用其它账号登录状态。
- 修复当前预约查询和取消预约时接口返回异常导致的报错提示不清晰问题。
- 新增账号管理页面，可查看已缓存账号、下线指定账号或一键下线全部账号。
- 补充隐私清理说明，账号、预约历史、座位映射缓存和 token 不应提交到公开仓库。

## 功能特点

- 支持 Gradio 前端界面预约座位。
- 支持命令行交互预约和取消预约。
- 支持 F6 图书室和华天图书馆常见座位预约。
- 支持预约前预热：
  - 提前登录账号；
  - 提前解析区域和座位 ID；
  - 提前建立连接；
  - 开抢时只提交预约请求，减少关键路径耗时。
- 支持本地密码缓存，已缓存账号无需重复输入密码。
- 支持查询当前账号预约记录，并在前端取消预约。
- 支持多账号预约列表；每个账号都会使用自己的密码缓存或本次填写的密码独立登录。
- 支持管理已缓存账号，可下线指定账号或一键下线全部账号。
- 支持停止预约，避免重复失败时继续请求。
- 支持本地静态缓存 `cache/space_id.json`、`cache/lib_set.json`，提升座位解析速度。
- Gradio 默认只监听 `127.0.0.1`，不会自动公开到外网。

## 环境要求

- Python 3.8+
- 推荐使用 Conda 虚拟环境

本项目开发验证环境：

```bash
Python 3.8.20
conda env: pachong
```

## 安装步骤

1. 克隆项目：

```bash
git clone https://github.com/GP-BYTE/neu-library-seat-reservation.git
cd neu_liberary_3_visualization
```

2. 创建并进入虚拟环境：

```bash
conda create -n pachong python=3.8 -y
conda activate pachong
```

如果你已有环境，也可以直接进入：

```bash
conda activate pachong
```

3. 安装依赖：

```bash
pip install -r requirements.txt
```

也可以使用 Conda 运行方式安装：

```bash
conda run -n pachong python -m pip install -r requirements.txt
```

4. 检查依赖：

```bash
python -m pip check
```

## 使用方式

### Gradio 可视化界面

启动前端：

```bash
python gradio_app.py
```

如果默认端口被占用，可以指定端口：

```bash
GRADIO_SERVER_PORT=8999 python gradio_app.py
```

启动后在浏览器打开终端显示的本地地址，通常是：

```text
http://127.0.0.1:7860
```

前端主要流程：

1. 输入学号。
2. 查看“密码缓存状态”。
3. 如果显示“需要输入”，填写密码。
4. 输入座位号、开始时间、结束时间。
5. 点击“添加预约信息”。
6. 可选：点击“预热/检查预约”。
7. 点击“开始预约”。
8. 如需终止当前任务，点击“停止预约”。

### 命令行预约

```bash
python run_order.py
```

根据提示选择预约或取消预约，并按要求输入学号、座位号和时间。

### 查询与取消预约

在 Gradio 前端进入“当前预约”页面：

1. 输入学号。
2. 如账号未缓存，输入该学号对应的密码；切换学号时密码框会自动清空，避免误用上一个账号密码。
3. 点击“查询当前预约”。
4. 选择要取消的预约。
5. 点击“取消所选预约”。

说明：程序不会使用账号 A 的登录状态查询或操作账号 B。查询、取消、预约都会按目标学号独立登录；如果账号 B 没有本地密码缓存，就需要填写账号 B 的密码。

### 账号管理

在 Gradio 前端进入“账号管理”页面：

1. 点击“刷新账号列表”查看本地已缓存账号。
2. 选择某个账号后点击“下线所选账号”，只删除该账号的本地密码缓存。
3. 点击“一键下线所有账号”，会清空所有本地密码缓存。

账号管理只展示学号，不展示密码或编码后的密码。

## 座位号说明

华天图书馆座位号通常类似：

```text
21624B
20701D
```

F6 图书室座位号通常类似：

```text
6B
06B
```

程序会兼容 `6B` 和 `06B` 这类格式差异。

## 本地文件说明

程序运行后可能生成以下本地文件：

```text
user_info.json          # 本地账号和编码后密码缓存
cache/history.json      # Gradio 历史预约输入记录
cache/space_id.json     # 图书馆区域 ID 缓存
cache/lib_set.json      # 座位 ID 映射缓存
schedule.json           # 本地计划任务数据
```

这些文件都不应该上传到 GitHub。项目的 `.gitignore` 已经默认忽略它们。

如果准备公开仓库，建议先删除个人数据：

```bash
rm -f user_info.json user_info.json.tmp cache/history.json schedule.json
rm -rf __pycache__ .idea
```

## 可选环境变量

如果登录接口需要初始化 token，可以设置：

```bash
export NSU_BOOTSTRAP_READER_TOKEN="your-bootstrap-token"
```

通常情况下不需要设置。

## 常见问题

### 1. Gradio 端口被占用

使用其他端口启动：

```bash
GRADIO_SERVER_PORT=8999 python gradio_app.py
```

### 2. 首次预约较慢

首次运行可能需要从网络获取图书馆区域和座位映射。建议先在前端点击“预热/检查预约”，预热完成后再开始预约。

### 3. pip check 提示 ffmpeg-python 缺少 future

如果你的环境出现类似提示：

```text
ffmpeg-python 0.2.0 requires future, which is not installed.
```

可以安装缺失依赖：

```bash
pip install future
```

这通常是当前 Python 环境已有包的问题，不是本项目核心功能依赖。

### 4. 账号密码是否会上传？

不会。账号缓存文件 `user_info.json` 已被 `.gitignore` 忽略。但如果你手动上传或复制该文件，仍可能泄漏个人信息。公开仓库前请确认本地隐私文件已经删除。

## 开发验证

语法检查：

```bash
python -m compileall -q .
```

依赖检查：

```bash
python -m pip check
```

关键依赖版本：

```bash
python -m pip show requests urllib3 pycryptodome gradio
```

## 免责声明

本项目仅用于学习和个人效率提升。请遵守学校图书馆预约系统规则，合理控制请求频率，不要将本工具用于破坏系统公平性或影响公共服务稳定性。

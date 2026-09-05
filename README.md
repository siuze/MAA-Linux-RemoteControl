# MAA-Linux-RemoteControl (MAA-LRC)

MAA-LRC 是一个基于 Python 实现的、专为无图形界面 Linux 设备（如树莓派、Orange Pi、RK3588 等嵌入式开发板及各类无头云服务器）量身打造的 [MAA (MaaAssistantArknights)](https://github.com/MaaAssistantArknights/MaaAssistantArknights) 远程调度控制系统。

- **WebSocket 双向长连接**：MAA-LRC 作为客户端主动连入控制中心（如 NoneBot2 机器人服务端），按队列自动接收并调度任务；
- **全生命周期回调上报**：任务启停、状态、执行耗时、基建汇报、掉落统计与图像截图均实现结构化通知闭环；
- **工业级防僵尸与资源自愈**：彻底解决多进程下 `defunct` 僵尸进程与脱壳孤儿进程问题；空闲 10 分钟优雅析构休眠并由系统 100% 回收 C++ / Python 物理内存。

---

## 核心特性

- [x] **空闲优雅休眠**：连续 10 分钟无未完成任务时，自动析构 `Asst` 实例并退出子进程释放全部内存，有新任务时自动拉起
- [x] **自动更新内核与资源**：启动前自动检测上游 Release 并静默拉取 aarch64 / x86_64 预编译包与 OTA 资源
- [x] **无线调试端口动态感知**：支持 Android 11+ 无线调试，连接断开或手机重启后自动通过 `nmap` 扫描局域网动态端口并重连
- [x] **全功能常规任务**：支持启动、关闭、自动作战（理智药/掉落汇报/企鹅物流）、公开招募、基建换班、信用商店、领取奖励与自定义任务
- [x] **中断配置与即时任务**：支持独立队列并发调度中断任务（如“立即截图”、“停止指定配置”、“紧急终止”），具备高响应性且不阻塞主队列
- [x] **次要配置动态让位**：支持配置优先级 `priority < 0`（仅区分负数次要配置与非负数主要配置，暂不做数值大小排序），挂机或长线作业时若检测到队列中有新的正常配置到达，自动中止当前次要配置让出执行权
- [x] **图像检测与基建预警**：支持自动获取任务前/后截图、长图拼接上报、自动检测限时活动签到/单抽遗漏、以及基建红色感叹号异常预警

---

## 运行效果展示（基于 NoneBot2 机器人回调通知）

| 自动检测升级与 OTA | 游戏启动与登录 | 作战结算与理智统计 |
| :---: | :---: | :---: |
| ![自动更新](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/e6f2adbd-c3d5-44de-844e-e5aa36ae70c0) | ![启动游戏](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/137c56c6-c3cd-47a8-8017-1189162501cc) | ![作战总结](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/05a246d8-2e5b-4560-9404-f0403ada1f12) |

| 基建入驻与心情排班 | 公开招募计算 | 信用商店购买 |
| :---: | :---: | :---: |
| ![基建排班](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/99689c39-4eb0-4c81-9033-b24b3c675100) | ![公开招募](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/ae16d811-26fb-4dca-ba1c-e0ae4704614d) | ![信用商店](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/7095b36f-7b7b-4b55-801c-4756eccad7bc) |

---

## 快速使用指引

> [!IMPORTANT]
> **操作系统版本强约束说明**：  
> **强烈要求不要使用太旧的 Linux 系统，发行版最低不能低于 Ubuntu 24.04 LTS**（或配备相同现代高版本 glibc 的 64 位 Linux）。  
> **原因**：MAA 官方 C++ 核心库（`libMaaCore.so`）及 AI OCR 推理引擎在官方流水线编译构建时链接了较高版本的系统 **glibc**。若在老旧系统（如 Ubuntu 20.04/22.04）上运行，将直接抛出 `version 'GLIBC_x.xx' not found` 致命动态链接错误；且**无法保证 MAA 上游后续版本更新时会不会需要更高版本的 glibc**。

### 1. 系统依赖安装
```bash
sudo apt update
sudo apt install -y adb nmap git tmux curl libatomic1 libgomp1
```

### 2. Python 运行环境搭建
推荐使用 `micromamba`、`conda` 或 `venv`（Python 版本建议 3.10 ~ 3.13）：
```bash
# 激活或创建虚拟环境（以 micromamba 为例）
micromamba activate maa

# 安装依赖
pip install -r requirements.txt
```
*(注：项目预置了 `opencv-python-headless`，切勿在无图形界面开发板上安装带 GUI 依赖的普通 opencv)*

### 3. 配置修改
复制或修改根目录下的 [config.yaml](./config.yaml)：
```yaml
connection:
  adb: adb                 # ADB 命令路径
  config: CompatPOSIXShell # Android 设备 Shell 模式
  ip: 192.168.31.200       # 目标安卓设备 IP
  port: 5555               # ADB 端口号
  scan_port: false         # Android 11+ 无线调试端口变动时设为 true

instance_options:
  touch_mode: maatouch     # 强烈推荐 maatouch 原生触控

python:
  debug: true              # 开启详尽轨迹日志
  auto_update: true        # 开启 MAA 内核与资源全自动更新（自动匹配 aarch64/x86_64）
  ws: ws://192.168.31.100:8068/maa # 服务端 WebSocket 地址
```

### 4. 运行与生产常驻（推荐：tmux + run.sh）
- **前台调试验证**：
  ```bash
  python __init__.py
  ```
- **生产无人值守守护（作者本人的实战方案）**：
  ```bash
  chmod +x run.sh
  ./run.sh
  ```
  > 守护脚本会自动循环检测并在名为 `maa` 的 tmux 会话中拉起主程序。  
  > 随时通过 `tmux a -t maa` 查看实时彩色行为日志；按快捷键 `Ctrl + B` 然后按 `D` 安全挂起断开。

---

## ⚠️ 关于任务配置与 MAA 官方参数的重要提示

> [!WARNING]
> **官方任务参数时效性声明**：  
> 1. MAA 官方任务的执行参数（`params`）会紧随 MAA 上游版本的演进、游戏内新机制（新活动模式、保全派驻、生息演算等）的引入而频繁变动；  
> 2. **本仓库 Wiki 中的参数说明与配置示例可能存在更新滞后或过时的情况**；  
> 3. 若您在下发任务时遇到参数无效、报错或需要配置最新关卡，请以：
>    - [MAA 官方集成文档 (3.1-集成文档.md)](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/master/docs/3.1-%E9%9B%86%E6%88%90%E6%96%87%E6%A1%A3.md)
>    - 本地 MAA 核心目录中 `resource/tasks/tasks.json`（或 `cache/resource/tasks.json`）  
>    给出的最新官方 Schema 定义为准！

---

## 官方 Wiki 文档中心

详细的技术实现原理、交互协议报文与进阶配置指南，请查阅 [本项目官方 Wiki](https://github.com/siuze/MAA-Linux-RemoteControl/wiki)：

- 🚀 **[快速开始与部署指南](https://github.com/siuze/MAA-Linux-RemoteControl/wiki/快速开始与部署指南)**：以 aarch64 开发板为基准的系统依赖、环境搭建与排查指引
- 📡 **[交互协议说明](https://github.com/siuze/MAA-Linux-RemoteControl/wiki/交互协议说明)**：WebSocket 双向协议规范、回执闭环与重连时序
- 📋 **[任务配置说明](https://github.com/siuze/MAA-Linux-RemoteControl/wiki/任务配置说明)**：官方/自定义任务字段字典、时段与条件表达式用法
- 🔔 **[通知消息说明](https://github.com/siuze/MAA-Linux-RemoteControl/wiki/通知消息说明)**：6 种主动推送通知结构与标准状态码定义
- ⚙️ **[运行过程说明](https://github.com/siuze/MAA-Linux-RemoteControl/wiki/运行过程说明)**：双隔离子进程架构模型、优雅休眠与防僵尸治理
- 💡 **[常见问题与重要提醒](https://github.com/siuze/MAA-Linux-RemoteControl/wiki/常见问题与重要提醒)**：自动更新原理、无线调试端口扫描与 tmux 实战

---

## 开发与贡献准则

欢迎提交 Issue 和 Pull Request！为了保证项目的易维护性，请严格遵守以下开发规范：
1. **缩进规范**：**必须使用制表符 (`Tab`) 进行代码缩进**，严禁使用空格缩进；
2. **代码检查**：提交前请使用 `ruff check .` 进行代码校验，根目录下已预置对齐 Tab 缩进的 [pyproject.toml](./pyproject.toml)；
3. **安全准则**：禁止在子模块中擅自调用 `os._exit(0)`，必须确保 `Asst` 实例能够通过 `destroy()` 正常析构并被操作系统回收。

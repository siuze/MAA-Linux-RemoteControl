# MAA-Linux-RemoteControl (MAA-LRC) 示例库说明

本目录提供了 MAA-LRC 的任务配置范例与机器人服务端集成示例。

---

## 目录结构

```text
example/
├── README.md               # 本说明文档
├── nonebot_example/        # NoneBot2 机器人服务端集成示例插件
│   ├── __init__.py         # 插件入口，注册 APScheduler 定时调度器
│   ├── maa.py              # Notice 通知报文解析与 QQ 消息链构建
│   ├── typeddef.py         # 任务配置与通知报文的 Type 提示定义
│   ├── ws.py               # WebSocket 服务端路由端点 (/maa) 与任务下发函数
│   └── data/               # 示例任务配置文件与资源存放目录
│       └── tasks_config.json # 完整的任务下发队列样例
└── tasks_example/          # 各类常见指令与任务配置的纯 JSON 范例
    ├── tasks_example.json  # 涵盖启动、签到、基建、战斗、公招、肉鸽等的完整配置
    ├── tasks_screenshot.json # 立即截图的中断任务 (interrupt)
    ├── tasks_stop.json     # 立即终止运行的中断任务
    └── tasks_stop_config.json # 停止当前运行配置的中断任务
```

---

## 一、NoneBot2 服务端插件示例 (`nonebot_example/`)

本示例演示了如何在 **NoneBot2** 框架中通过内置驱动器（如 FastAPI / Quart）暴露一个 `/maa` WebSocket 路由，作为远端控制服务端接收开发板上的 MAA-LRC 客户端连接。

### 核心功能
1. **WebSocket 服务端路由（`ws.py`）**：
   - 监听 `ws://<host>:<port>/maa`；
   - 支持向 MAA 客户端下发 `TaskConfig` 任务配置（如触发立即截图或下发定时日常刷图配置）。
2. **消息通知与上报（`maa.py`）**：
   - 接收 MAA 客户端上报的 `Notice` 报文（`task_result`、`config_start`、`config_end`、`update_log` 等）；
   - 自动解析耗时与执行状态，将任务截图（Base64 转 bytes）拼装进消息链推送到指定的 QQ 群或私聊。
3. **定时任务调度（`__init__.py`）**：
   - 基于 `nonebot_plugin_apscheduler` 在每天指定时刻（如凌晨 4:00、中午 12:00、晚上 20:00）自动读取 `data/tasks_config.json` 并逐项下发执行。

---

## 二、任务配置 JSON 范例 (`tasks_example/`)

若您开发自己的后端系统（如使用 Node.js、Go、Java、FastAPI 等），可参考本目录下的标准 JSON 格式生成任务报文：

### 1. 紧急中断与即时任务（`type: "interrupt"`）
- **立即截图**（[tasks_screenshot.json](tasks_example/tasks_screenshot.json)）：
  ```json
  [
    {
      "id": "立即截图",
      "type": "interrupt",
      "tasks": [
        {
          "type": "Screenshot",
          "name": "立即截图"
        }
      ]
    }
  ]
  ```
- **立即终止**（[tasks_stop.json](tasks_example/tasks_stop.json)）：
  用于紧急停止 MAA 当前所有任务并阻断后续执行。

### 2. 标准日常流程任务（`type: "normal"`）
参考 [tasks_example.json](tasks_example/tasks_example.json)：
- 包含 `CloseDown`（清理重启）、`StartUp`（登录唤醒）、`Infrast`（基建换班与收获）、`Fight`（作战及特定星期刷材料判断）、`Recruit`（公开招募）、`Mall`（信用商店购买）等完整链条；
- 包含 `condition` 条件过滤器（`weekday`、`hour`）与 `block: "executed"` 依赖阻断用法。

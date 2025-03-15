# MAA-Linux-RemoteControl
就简称MAA-LRC吧

## MAA-LRC使用Python实现无图形界面设备下远程控制[MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights)，运行明日方舟助手
 - 利用Websocket协议通信，MAA-LRC作为客户端连接到远程控制的服务端，对服务端下发的任务配置进行队列处理
 - 对每个子任务的运行结果进行回调报告，可以加入截图一并汇报

## 目前已实现
 - [x] 空闲超过10分钟以上时，释放相关内存资源进入休眠（通过重启子进程来实现）   
 - [x] 执行任务前自动更新MAA版本和OTA资源   
 - [x] 支持Android 11+设备的无线调试连接（端口扫描和自动重连）   
 - [x] 运行MAA的常规任务（启动、关闭、作战、公招、基建、领取奖励和自定义任务）  
 - [x] 作战结果与掉落物品日志记录  
 - [x] 获取任务运行前/后截图  
 - [ ] 获取基建入驻总览的截图  
 - [x] 获取基建副手简报的截图  
 - [x] 获取日常周常奖励页面截图  
 - [x] 获取公招界面的截图  
 - [x] 发送截图和日志到服务端进行汇报  
 - [x] 任务运行时立即获取实时截图  
 - [x] 任务运行时立即中断运行  
 - [x] 自动检查是否存在签到活动尚未领取的情况（只在中午12点后执行任务时检查）  
 - [x] 自动检查是否存在赠送单抽机会尚未使用的情况  
 - [x] 自动检查基建是否存在异常情况（红色三角警告标志）（只是检查，不是自动处理）  




## 运行效果（使用Nonebot构建的QQ机器人下对MAA-LRC推送的回调消息进行通知）
激活MAA时自动更新  
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/e6f2adbd-c3d5-44de-844e-e5aa36ae70c0)

 
启动游戏  
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/137c56c6-c3cd-47a8-8017-1189162501cc)
  
作战总结  
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/05a246d8-2e5b-4560-9404-f0403ada1f12)
  
基建排班  
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/99689c39-4eb0-4c81-9033-b24b3c675100)
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/a46ad2a0-d7c5-4c9d-9d6f-4a47b2573f73)
  
基建简报   
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/2b0838c0-98f0-495e-8aeb-6d325a6fdc7d)

信用商店  
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/7095b36f-7b7b-4b55-801c-4756eccad7bc)

公开招募  
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/ae16d811-26fb-4dca-ba1c-e0ae4704614d)
![%7BAAF74C4D-043F-4c1b-9266-5E13139B571C%7D](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/a75b0408-30c7-4138-ab70-bb7019bc0f1d)



任务奖励    
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/9a1b2688-addf-4db0-987c-981decfb33a3)



## 使用方法
 1. 下载MAA官方的[linux发布版本](https://github.com/MaaAssistantArknights/MaaAssistantArknights/releases)，解压后放在某某路径（第一次执行的时候需要手动下载，之后就不用了）；  
 2. 下载本项目源码；  
 3. 修改源码根目录下的 [config.yaml](./config.yaml) 以适应自己的情况；  
 4. 安装好Python环境，目前项目仅在python3.13下实际运行测试过，不完全保证其他版本的兼容性；  
 5. 参考 [requirement.txt](./requirements.txt) 安装Python的第三方库；  
 6. 在源码的根目录下执行  

```shell
   python __init__.py
```

> 不想自己研究的话也可以加入我的MAA代挂托管群（275264699），一个月4块(๑╹◡╹)ﾉ"""

## 交互协议说明
见[本项目wiki](https://github.com/siuze/MAA-Linux-RemoteControl/wiki/交互协议说明)
## 任务配置说明
见[本项目wiki](https://github.com/siuze/MAA-Linux-RemoteControl/wiki/任务配置说明)
## 通知消息说明
见[本项目wiki](https://github.com/siuze/MAA-Linux-RemoteControl/wiki/通知消息说明)
## 运行过程说明
见[本项目wiki](https://github.com/siuze/MAA-Linux-RemoteControl/wiki/运行过程说明)
## 常见问题与重要提醒
见[本项目wiki](https://github.com/siuze/MAA-Linux-RemoteControl/wiki/常见问题与重要提醒)

## 另外的
  
我的代码水平很差，欢迎各种issue和pr。  
唯有一点：请使用tab进行代码缩进，如非必要，不使用空格实现缩进。  
建议使用ruff进行代码格式化   

# MAA-Linux-RemoteControl
就简称MAA-LRC吧

## MAA-LRC使用Python实现无图形界面设备下远程控制[MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights)，运行明日方舟助手
 - 使用Websocket作为客户端连接到远程控制的服务端，对服务端下发的任务配置进行队列处理
 - 对每个子任务的运行结果进行回调报告，可以加入截图一并汇报

## 目前已实现
 - [ ] 没有任务等待运行时释放相关内存资源进入休眠（虽然有进行删除实例和内存回收工作，但还是有内存泄漏问题，目前的妥协方案是在任务队列清空后自动退出进程）   
 - [x] 下发任务时自动更新MAA版本和OTA资源   
 - [ ] MAA内核版本更新后热重载相关进程资源  
 - [x] 支持Android 11+设备的无线调试连接（端口扫描和自动重连）   
 - [x] 运行MAA的常规任务（启动、关闭、作战、公招、基建、领取奖励和自定义任务）  
 - [x] 作战结果与掉落物品汇总汇报  
 - [x] 获取任务运行前后截图  
 - [x] 获取基建入驻总览的截图  
 - [x] 获取基建副手简报的截图  
 - [x] 获取日常周常奖励页面截图  
 - [x] 获取公招界面的截图  
 - [x] 发送截图和日志到服务端进行回调报告  
 - [x] 任务运行时立即获取实时截图  
 - [x] 任务运行时立即中断运行  
 - [x] 自动检查是否存在签到/合成玉抽签活动尚未领取的情况（只是检查，不是自动领取）  
 - [x] 自动检查是否存在大型活动赠送单抽机会尚未使用的情况（只是检查，不是自动用掉）  
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
### 1、下载MAA的[linux发布版本](https://github.com/MaaAssistantArknights/MaaAssistantArknights/releases)，解压后放在某某路径
### 2、下载本项目源码
### 3、**修改源码文件夹 `config-example` 的名字为 `config`**
### 4、阅读并按自己需求修改 [`config`](./config_example/) 文件夹下的配置文件 [`asst.yaml`](./config_example/task.yaml)  

### 5、检查安装python的依赖包，我所用的是Python 3.10.13
```
aiohttp==3.9.1
loguru==0.7.2
PyYAML==6.0.1
requests==2.31.0
websocket-client==1.7.0
opencv-python-headless==4.9.0.80
```
### 6、运行
在项目主文件夹下运行：
```
python __init__.py
```


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

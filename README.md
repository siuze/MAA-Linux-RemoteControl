# MAA-Linux-Python

## 旨在寻求方法，通过Linux下的Python脚本运行[MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights)任务以实现：
 - 在无界面的Linux设备 + 一台安卓真机/模拟器下运行MAA
 - 能够对任务结果整理和截图，进行通知推送

## 目前已实现
 [x] 自动更新MAA版本和OTA  
 [x] 运行MAA的常规任务（作战、基建、领取奖励等）  
 [x] 获取任务运行前后截图  
 [x] 获取基建入驻总览的截图（增加了一些自定义任务动作）  
 [x] 获取基建副手简报的截图（增加了一些自定义任务动作）  
 [x] 发送截图和日志到指定的请求地址实现通知消息  

## 运行效果（通知效果）
![QQ截图20231213104405](https://github.com/siuze/MAA-Linux-Python/assets/54578647/9c0c3a5f-d716-4d09-9fa2-f7b9f7b76d14)
![QQ截图20231213104523](https://github.com/siuze/MAA-Linux-Python/assets/54578647/2408eda2-e384-430a-be92-b472cde3cdf4)
![QQ截图20231213104321](https://github.com/siuze/MAA-Linux-Python/assets/54578647/e829e1ef-9df5-4a4a-a9c8-43ca083608d7)
![QQ截图20231213104450](https://github.com/siuze/MAA-Linux-Python/assets/54578647/66c6084a-cf7c-4534-a8e8-6a3e86bc31f0)
![QQ截图20231213104505](https://github.com/siuze/MAA-Linux-Python/assets/54578647/6b00bfe4-a77f-46a2-a1ca-2b81e331bf00)


## 使用方法
### 1、下载MAA的[linux发布版本](https://github.com/MaaAssistantArknights/MaaAssistantArknights/releases)，解压后放在某某路径（这一步是不是必须的我不知道，也许这个脚本面对空文件夹也能自动下载更新，我还没试过）
### 2、下载本项目源码
### 3、**修改源码文件夹`config-example`的名字为`config`**
### 4、阅读并修改[`config`](./config_example/)文件夹下的几个配置文件，[`task.yaml`](./config_example/task.yaml)可以不动，但是[`asst.yaml`](./config_example/task.yaml)一定要自己配置好

###

### 5、检查python的依赖包，我所用的是Python 3.10.13
```
loguru==0.7.2
PyYAML==6.0.1
Requests==2.31.0
```
### 6、运行
```
python maa.py
```


## 已知问题
 - 使用`Ctrl+C`强制退出程序后再次运行时报出C的内存相关错误`double free or corruption (out)`，目前就暂时多退出再运行几次吧
  
    
  

## 另外的
### 	Q: 不是已经有[`Maa-Cli`](https://github.com/MaaAssistantArknights/maa-cli/releases/latest)了吗？
`Cli`是用`Rust`写的，我不怎么会，所以就参照`MAA`官方的[`sample.py`](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev/src/Python/sample.py)用`python`写了一下。  
毕竟目前Cli的输出结果如果要实现推送的话还是要外接一些东西的，而且暂时也没截图功能。所以想着干脆直接用python调API算了，也更好调试一些。   
  
我的代码水平很差，欢迎各种issue和pr。  

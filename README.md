# MAA-Linux-RemoteControl
就简称maa-lrc吧

## maa-lrc使用Python实现无图形界面设备下远程控制[MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights)，运行明日方舟助手
 - 使用Websocket作为客户端连接到远程控制的服务端，对服务端下发的任务配置进行队列处理
 - 对每个子任务的运行结果进行回调报告，可以加入截图一并汇报

## 目前已实现
 - [x] 没有任务等待运行时释放相关内存资源进入休眠   
 - [x] 下发任务时自动更新MAA版本和OTA资源   
 - [x] 支持Android 11+设备的无线调试连接（端口扫描和自动重连）   
 - [x] 运行MAA的常规任务（启动、关闭、作战、公招、基建、领取奖励和自定义任务）  
 - [x] 作战结果与掉落物品汇总汇报  
 - [x] 获取任务运行前后截图  
 - [x] 获取基建入驻总览的截图（增加了一些自定义任务动作）  
 - [x] 获取基建副手简报的截图（增加了一些自定义任务动作）  
 - [x] 获取日常周常奖励页面截图（增加了一些自定义任务动作）  
 - [x] 获取公招界面的截图（增加了一些自定义任务动作）  
 - [x] 发送截图和日志到服务端进行回调报告  
 - [ ] 立即获取实时截图  
 - [ ] 立即中断运行  




## 运行效果（通知效果）
![QQ截图20231213104405](https://github.com/siuze/MAA-Linux-Python/assets/54578647/9c0c3a5f-d716-4d09-9fa2-f7b9f7b76d14)
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/f63fd0d4-05c9-4963-8004-41ed78ec53f5)
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/eccf2591-7ec4-4f74-b8cc-ee31e2df92bb)
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/31ac2862-7034-402c-a591-9d6d5f724370)
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/4f7b33eb-6f7c-4f9b-aff9-d8209d48ade0)

![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/8add8f59-55e6-4589-9697-4d8e1097d3ea)
![image](https://github.com/siuze/MAA-Linux-RemoteControl/assets/54578647/73c13f00-205b-4419-a36a-ae1212a7e697)


## 使用方法
### 1、下载MAA的[linux发布版本](https://github.com/MaaAssistantArknights/MaaAssistantArknights/releases)，解压后放在某某路径
### 2、下载本项目源码
### 3、**修改源码文件夹`config-example`的名字为`config`**
### 4、阅读并按自己需求修改[`config`](./config_example/)文件夹下的配置文件，[`asst.yaml`](./config_example/task.yaml)  

### 5、检查安装python的依赖包，我所用的是Python 3.10.13
```
aiohttp==3.9.1
loguru==0.7.2
PyYAML==6.0.1
requests==2.31.0
websocket-client==1.7.0
```
### 6、运行
```
python maa.py
```

## 交互协议
### 服务端下发任务
maa-lrc作为客户端，允许接收服务端下发的json格式的文本，其要求的协议格式参考了MAA-WIN-GUI端的协议要求，并做了一些改动。   
maa-lrc每次只能接收一个json文本，并会解析为一个任务配置加入等待运行的队列中。一个任务配置里面可以有很多子任务。每次只能接收一个配置，等待运行的队列将会按照加入先后顺序完成每个配置。   
配置主要格式如下：    
 - **请参阅[tasks_example.json](./tasks_example.json)获取更多任务配置说明**    
 - **json不能有注释，请注意删去！**  
 - 选填的意思是这个键值对可以不用加入，而不是说可以写成诸如 "key":null 的形式

``` json
	{
	"name": "这份配置的名称，选填",
	"tasks": 	//子任务序列，将依次执行这里面的任务
		[
			{
				"type": "StartUp",	//必填，任务类型，支持任务类型见下
				"id": "明日方舟启动", //选填，任务的名称，汇报任务结果的时候会附带
				"screenshot": "after", //选填，是否在任务运行前后截图并汇报 before | after，
				"params": 	//选填，任务的参数 参照官方文档的要求来
						{
						"client_type": "Official",
						"start_game_enabled": true
						}
			},
			{
				"type": "Fight",
				"id": "每周剿灭",
				"enable": false, //选填，表示是否运行该任务
				"screenshot": "after",
				"params": {
							"expiring_medicine": 1000,
							"stage": "Annihilation",
							"times": 5
						},
				"condition": //选填，表示在什么条件下运行
						{
						"weekday":  //选填，列表，
								[
									1, //只有当星期一，星期天的时候才运行该任务
									7,
								],
						"hour":	//选填
							{
								"<": 18 //<或>，只有当时间小于18:00的时候才运行该任务
							}
						},
			},
			{
				"type": "Award",
				"params": {
				"award": true,
				"mail": true	//领取邮件，这个功能说明官方文档似乎还没跟进
				}
			},
			{
				"type": "Custom",
				"id": "日常任务",
				"screenshot": "after",
				"params": {
					"task_names": [//填写最小任务动作
						"进入日常任务"	//下面这几个这是我自定义的任务动作，实现在日常周常建立界面截图的功能
					]
				}
			},
			{
				"type": "CloseDown"
			}
	]
  }
```
#### 目前支持的任务：    
#### 【官方任务】  
请参考MAA官方的[集成文档](https://maa.plus/docs/%E5%8D%8F%E8%AE%AE%E6%96%87%E6%A1%A3/%E9%9B%86%E6%88%90%E6%96%87%E6%A1%A3.html)填写任务参数   
 - StartUp 开始唤醒  
 - CloseDown 关闭游戏  
 - Fight 刷理智  
 - Recruit 公开招募  
 - Infrast 基建换班  
 - Mall 领取信用及商店购物  
 - Award 领取日常奖励  
 - Custom 自定义任务  
> 请注意： 进驻 | 简报 | 公招 | 日常 | 周常 等界面截图任务是由一系列自定义任务下调用maa-lrc自定义的任务动作实现的，自适应性可能差，请尽可能紧跟在对应的官方任务后面运行。
  
以下官方任务理论上也能用，但是我尚未测试过  
 - Roguelike 无限刷肉鸽 (尚未测试过)  
 - Copilot 自动抄作业  
 - SSSCopilot 自动抄保全作业  
 - Depot 仓库识别  
 - OperBox 干员 box 识别  
 - ReclamationAlgorithm 生息演算  
 - SingleStep 单步任务  
 - VideoRecognition 视频识别  



#### 本项目中新增的任务：  
 - Update 更新MAA版本，这个任务一般不用加在日常配置里面，因为每次激活MAA都会自动检查并更新版本。   
 - Screenshot 立即获取截图（尚未实现）  
     
  




### 客户端上报消息
客户端主要在子任务完成后上报消息，展示运行结果，上报的消息是一条json文本，其协议格式如下。  
```json
{
	"devices": "00E0F192A9D", //maa-gui-rc的协议里原本是MAA自动生成的设备标识符，我这里就简单设置为设备MAC地址
	"user": "",//maa-gui-rc里为用户在MAA设置中填写的用户标识符，这里直接留空暂时不作处理
	"task": "Fight_5",//上报的子任务的id，如果配置里没提供的话就是 type_任务序号 的形式
	"task_type": "Fight", //上报的子任务类型
	"status": "SUCCESS", //运行结果，目前出错识别尚未完善，大多数时候都是SUCCESS，少数时候是FAILED
	"payload": "作战结果：\n  RS-5 * 1 \n战斗掉落：\n  驮兽盲盒 * 12\n  固源岩 * 2\n  龙门币 * 144",  //日志文本信息，基本上没什么日志，maa-gui-rc里还会放图片，这里不会，图片放在下面的image里面
	"image": "iVBORw0KGgoAAAANSUhEUgAABQAAA...", //截图，如果有的话是图片的base64编码，没有的话就是空字符串""
	"duration": 300, //任务运行耗时，单位秒
	"type": "recall", //消息类型 一般为任务汇报消息"recall"
	"name": config_name
}
```
或
```json
	{
			"status": "SUCCESS",
			"payload": "MAA已收到一条任务配置，加入任务处理队列中逐个运行",
			"type": "receipt", //服务器下发的消息收到后的回执"receipt"
		}
```
或
```json
	{
			"payload": "日志内容"
			"type": "notice", //一些日志通知，目前只有MAA激活的时候的版本更新日志
		}
```

## 运行过程简要说明
程序主要通过全局变量来进行内部沟通，包含：  
 - tasks_config_waiting_list
 - send_msg_waiting_list
 - my_maa
 - wsapp
  
    
脚本会创建三个线程：
 - **WS客户端线程**：维护wsapp客户端，实现保持ws连接。收到消息时，会把解析出来的配置加入到tasks_config_waiting_list队列中。   
 - **WS待发送消息队列**：循环检查send_msg_waiting_list中有没有未发送的消息，有的话将取出并调用wsapp发送发消息   
 - **MAA任务配置处理队列**：循环检查tasks_config_waiting_list中有没有未处理的任务配置，有的话将其取出并激活MAA运行任务，没有的话就删除MAA实例释放内存进入休眠  

> **请不要随意删除线程循环检查中的sleep方法,这会导致CPU占用很高**
    

## 已知问题
 - 使用`Ctrl+C`强制退出程序后重新运行时可能报出C的内存相关错误`double free or corruption (out)`，目前就暂时多强制退出再运行几次吧   
 - ws的重连和错误处理尚不完善   
  
    
  

## 另外的
### 	Q: 不是已经有[`Maa-Cli`](https://github.com/MaaAssistantArknights/maa-cli/releases/latest)了吗？
`Cli`是用`Rust`写的，我不怎么会，所以就参照`MAA`官方的[`sample.py`](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev/src/Python/sample.py)用`python`写了一下。  
毕竟目前Cli的输出结果如果要实现推送的话还是要外接一些东西的，而且暂时也没截图功能。所以想着干脆直接用python调API算了，也更好调试一些。   
  
我的代码水平很差，欢迎各种issue和pr。  

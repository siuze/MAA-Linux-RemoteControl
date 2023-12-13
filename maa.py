from pathlib import Path
import os
import json
import time
import datetime
import yaml
import asyncio
from loguru import logger as lg
from asst.asst import Asst
from asst.utils import Message, Version, InstanceOptionType
from asst.updater import Updater

from Qmsg import send_msg
# from Qmsg import send_qqimagedeliver as send_msg

#记录日志
lg.add(str(Path(__file__).parent / "logs/log_{time}.log"), rotation="1 day")



@Asst.CallBackType
def my_callback(msg, details, arg) -> None:
	"""
	MAA-CORE的运行消息回调函数
	:params:
		``msg``: 消息类型
		``details``:  消息具体内容
	:return: None
	"""
	m = Message(msg)
	js = json.loads(details.decode('utf-8'))
	if msg == Message.InternalError or msg == Message.SubTaskError or msg == Message.TaskChainError:
		text = f"MAA出错：{str(m)} {details.decode('utf-8')}"
		lg.error(text)
		send_msg(text)
		exit(1)
	if 'what' in js:
		what = js['what']
		if what == 'UuidGot':
			text = f"获取到ADB设备uuid：{js['details']['uuid']}"
			lg.info(text)
			maa.start_log += text + '\n'
			#maa 明明是在后面定义的呀，很怪，但是确实能跑（本代码依赖bug运行，修的话就要把这些日志变量调到全局去了）
		elif what == 'ResolutionGot':
			text = f"获取到ADB设备分辨率：{js['details']['height']} X {js['details']['width']}"
			lg.info(text)
			maa.start_log += text + '\n'
		elif what == 'StageDrops':
			maa.add_fight_msg(js['details'])
		elif what == 'ScreencapFailed':
			text = f"截图失败，可能是ADB配置出现问题或Android 11无线调试变化了端口，尝试重新连接"
			lg.info(text)
			maa.reconnect()
	if maa.asst_config['python']['debug']:
		lg.info(m)
		lg.info(js)


class MAA:
	def __init__(self) -> None:
		self.start_log = 'MAA 明日方舟\n'	#启动信息
		self.singal_task_log = ''			#单个任务的信息
		self.fight_log = {'stages':{},'drops':{},'msg':''}	#作战信息
		self.stop_tag = '正常'	#任务运行完成后会检查回调函数有没有给出报错，有的话重新执行
		#MAA核心路径
		self.core_path = Path(__file__).parent.parent / "MAA-linux"
		os.environ['LD_LIBRARY_PATH'] = str(self.core_path)
		#更新版本
		update_log = Updater(self.core_path, Version.Beta).update()
		self.start_log += update_log
		#添加自定义任务模块
		self.add_custom_tasks()
		#加载资源
		Asst.load(path=self.core_path, incremental_path=self.core_path / 'cache')
		#构造并设置回调函数
		self.asst = Asst(callback=my_callback)
		#获取maa内核配置
		self.asst_config_path = str(Path(__file__).parent / "config/asst.yaml")
		with open(self.asst_config_path, 'r', encoding='utf8') as config_f:
			self.asst_config = yaml.safe_load(config_f)
		#获取maa任务配置
		self.tasks_path = str(Path(__file__).parent / "config/task.yaml")
		with open(self.tasks_path, 'r', encoding='utf8') as tasks_f:
			self.tasks = yaml.safe_load(tasks_f)
		#设置触控方式
		self.asst.set_instance_option(InstanceOptionType.touch_type, self.asst_config['instance_options']['touch_mode'])



	def add_custom_tasks(self):	
		"""
		将自定义的任务动作合并到官方的文件中
		"""
		custom_tasks_path = Path(__file__).parent / "custom/tasks.json"
		custom_tasks_path = self.core_path / "resource/tasks.json"

		with open(custom_tasks_path, 'r', encoding='utf8') as file:
			customs_tasks = json.load(file)	#读取自定义任务动作
		with open(custom_tasks_path, 'r', encoding='utf8') as file:
			official_tasks = json.load(file)	#读取官方任务动作
		for key, values in customs_tasks.items():
			official_tasks[key] = values	##自定义任务动作加入到官方配置并保存
		with open(custom_tasks_path, 'w',encoding='utf8') as file:
			file.write(json.dumps(official_tasks, ensure_ascii=False, indent=4, separators=(', ', ': ')))


	def find_adb_wifi_port(self):
		"""
		Android 11以上可以在开发人员选项内开启无线调试
		但是端口隔一段时间会变化，所以要扫描一下
		"""
		f=os.popen(f'nmap {self.asst_config["connection"]["ip"]} -p 30000-49999 | awk "/\\/tcp/" | cut -d/ -f1')  # 返回的是一个文件对象
		port = f.read().replace(' ','').replace('\n','')
		text = f"扫描得到ADB端口为：{port}"
		lg.info(text)
		self.start_log += text + '\n'
		with open(self.asst_config_path,'w',encoding='utf8') as config_f:
			yaml.dump(self.asst_config, config_f, allow_unicode=True)
		if not port:
			text = "扫描不到设备ADB端口，请排查"
			lg.error(text)
			send_msg(text)
			exit(1)
		self.asst_config["connection"]["port"] = int(port)

	def connect(self):
		"""
		通过ADB连接到安卓设备
		"""
		#获取ADB端口
		if self.asst_config['connection']['scan_port']:
			self.find_adb_wifi_port()

		text = f'尝试连接到：{self.asst_config["connection"]["ip"]}:{self.asst_config["connection"]["port"]}'
		lg.info(text)
		self.start_log += text + '\n'

		if self.asst.connect(	adb_path = self.asst_config["connection"]["adb"], 
								address = f'{self.asst_config["connection"]["ip"]}:{self.asst_config["connection"]["port"]}', 
								config = self.asst_config["connection"]["config"]
							):
			text = '连接成功'
			lg.info(text)
			self.start_log += text + '\n'
			send_msg(self.start_log)

			# await self.screenshot('连接成功后')
			# print("开始测试截图")
			# time.sleep(5)
			# print("结束测试截图")
			# await self.screenshot('测试结束后')
			# exit()
		else:
			text = f'连接失败，请检查MAA-CORE的日志，应当位于 {self.core_path}/debug/asst.log'
			lg.error(text)
			self.start_log += text + '\n'
			send_msg(self.start_log)
			exit(1)

	def reconnect(self):
		self.start_log = 'ADB连接出错，尝试重连\n'
		self.stop_tag = '需要重连'
		self.asst.stop()

	async def screenshot(self,file_name,rb=False): 
		"""
		调用MAA-CORE的API获取截图
		这个不是立即截图，只是获取任务运行的最近一张截图，怎么立即截图我还没研究出来
		:params:
			``file_name``: 截图保存的文件名
			``rb``:  是否返回图片文件的二进制bytes数组
		:return: 图片文件bytes[] | None
		"""
		img,length = await self.asst.screenshot()
		print(f"截图大小{length/1024}KBytes")
		with open(f'img/{file_name}.png','wb') as f:
			f.write(img[:length])
		if rb:
			return img
		else:
			return length



	def add_fight_msg(self, detail):
		"""
		对回调函数收到的作战结果进行解析
		:params:
			``details``:  消息具体内容
		:return: None
		"""
		stage = detail["stage"]["stageCode"]
		if stage not in self.fight_log['stages']:
			self.fight_log['stages'][stage] = 1
		else:
			self.fight_log['stages'][stage] += 1
		for drop in detail['stats']:
			self.fight_log['drops'][drop['itemName']] = drop['quantity']
		self.fight_log['msg'] = '作战结果：\n'
		for key,value in self.fight_log['stages'].items():
			self.fight_log['msg'] += f"  {key} * {value}\n"
		self.fight_log['msg'] += '战斗掉落：\n'
		for key,value in self.fight_log['drops'].items():
			self.fight_log['msg'] += f"  {key} * {value}\n"
		while self.fight_log['msg'][-1:] == '\n':
			self.fight_log['msg'] = self.fight_log['msg'][:-1]

	async def run_tasks(self):
		"""
		逐个运行任务配置中填写的任务
		"""
		task_count = 0 #第task_count个任务
		latest_official_task_count = 0 #记录最近执行的一个非custom任务的序号
		while(task_count < len(self.tasks['tasks'])):
			task = self.tasks['tasks'][task_count]
			task_id = task_count
			task_count += 1

			if 'id' in task:
				task_id = task['id']
			if task['type'] != 'Custom':
				latest_official_task_count = task_count

			#重置单个任务日志
			self.fight_log = {'stages':{},'drops':{},'msg':''}
			self.singal_task_log = ''
			text = f"【任务：{task['type']}_{task_id}】"
			lg.info(text)
			self.singal_task_log += text + '\n'

			#检查任务是否启用
			if 'enable' in task and task['enable'] == False:
				lg.info("该任务未启用，跳过")
				continue
			if 'condition' in task:
				now = datetime.datetime.now()
				if 'weekday' in task['condition']:
					if now.weekday()+1 not in task['condition']['weekday']:
						lg.info("未达到该任务启用的星期范围，跳过")
						continue
				if 'hour' in task['condition']:
					if '<' in task['condition']['hour'] and  now.hour >= task['condition']['hour']['<']:
						lg.info("时刻超过任务启用的范围，跳过")
						continue
					if '>' in task['condition']['hour'] and  now.hour <= task['condition']['hour']['>']:
						lg.info("时刻未达任务启用的范围，跳过")
						continue
						
			
			#加入任务队列中
			if "params" in task:
				self.asst.append_task(task['type'], task['params'])
			else:
				self.asst.append_task(task['type'])

			#运行前截图
			img_msg = None
			if "screenshot" in task and (task['screenshot'] == 'before' or task['screenshot'] =='both'):
				img_msg = await self.screenshot(f"before_{task['type']}_{task_id}",rb=True)

			#启动运行
			self.asst.start()
			while self.asst.running():
				time.sleep(0)

			if self.stop_tag == '需要重连':
				self.connect()	#任务运行过程出错，重新尝试连接到adb
				self.stop_tag == '正常'
				task_count =  latest_official_task_count  #回到最近一次的非自定义任务，因为自定义任务目前还没办法自适应。必须跟在官方任务之后执行
				continue
			#运行后截图
			if "screenshot" in task and (task['screenshot'] == 'after' or task['screenshot'] =='both'):
				img_msg = await self.screenshot(f"after_{task['type']}_{task_id}",rb=True)

			lg.info(f"【任务 {task['type']}_{task_id} 结束】")

			#发送任务日志和截图
			if 'notice' in task and task['notice'] == True:
				send_msg(self.singal_task_log + self.fight_log['msg'],img = img_msg)

			self.asst.stop()

	async def run(self):
		"""
		入口函数，连接和运行任务
		"""
		self.connect()
		await self.run_tasks()

maa = MAA()
loop = asyncio.get_event_loop()
result = loop.run_until_complete(maa.run())
loop.close()
# maa.run()
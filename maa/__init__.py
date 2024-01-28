import faulthandler
faulthandler.enable()
from pathlib import Path
import os
import json
import time
import datetime
import yaml
import uuid
import traceback
import subprocess
import base64
from loguru import logger as lg
import gc
import uuid
from cache import save_cache

from asst.asst import Asst
from asst.utils import Message, Version, InstanceOptionType
from asst.updater import Updater

from _global import global_var

facility_map = {
	"Mfg": "制造站",
	"Trade": "贸易站",
	"Power": "发电站",
	"Control": "控制中枢",
	"Reception": "会客室",
	"Office": "人力办公室",
	"Dorm": "宿舍"
}


@Asst.CallBackType
def my_callback(msg, details, arg) -> None:
	"""
	MAA-CORE的运行消息回调函数
	:params:
		``msg``: 消息类型
		``details``:  消息具体内容
	:return: None
	"""
	my_maa = global_var.get("my_maa")
	m = Message(msg)
	js = json.loads(details.decode('utf-8'))
	if m == Message.InternalError or m == Message.SubTaskError or m == Message.TaskChainError:
		text = f"MAA出错：{str(m)} {details.decode('utf-8')}"
		lg.error(text)
		if m == Message.TaskChainError and (js["taskchain"] in ["StartUp", "Award", "Mall" ]):
			my_maa.stop_tag = '任务链出错'
			my_maa.asst.stop()
		# send_msg(text) #先不发送了，防止刷屏消息被封
		# if  maa.stop_tag != 'MAA出错':
		# 	maa.stop_tag = 'MAA出错'
		# 	maa.asst.stop()
		# exit(1)
	if m == Message.AsyncCallInfo:
		text = f"收到异步调用的回调消息：{str(m)} {details.decode('utf-8')}"
		# maa.waiting_async.remove(js['async_call_id'])
		lg.info(text)
		
	if 'what' in js:
		what = js['what']
		if what == 'UuidGot':
			text = f"获取到ADB设备uuid：{js['details']['uuid']}"
			lg.info(text)
			my_maa.connect_log += text + '\n'
			#mymaa 明明是在后面定义的呀，很怪，但是确实能跑（本代码依赖bug运行）
		elif what == 'ResolutionGot':
			text = f"获取到ADB设备分辨率：{js['details']['height']} X {js['details']['width']}"
			lg.info(text)
			my_maa.connect_log += text + '\n'
		elif what == 'StageDrops':
			my_maa.add_fight_msg(js['details'])
		elif what == 'ScreencapFailed' and my_maa.stop_tag != '需要重连':
			text = f"截图失败，可能是ADB配置出现问题或Android 11无线调试变化了端口，尝试重新连接"
			lg.info(text)
			my_maa.stop_tag = '需要重连'
			my_maa.asst.stop()
		elif what == 'RecruitSpecialTag':
			my_maa.recruit_log += f"识别到稀有标签：【{js['details']['tag']}】\n"
		elif what == 'RecruitResult':
			if js['details']['level'] >= 5:
				my_maa.recruit_log += f"!重要!  存在五星或以上的公招标签组合，请在任务结束后检查：\n"
				result =js['details']['result']
				for match in result:
					if match["level"] >= 5:
						tags = "【 "
						for tag in match["tags"]:
							tags += tag+' '
						tags += '】'
						my_maa.recruit_log += tags 
						for oper in match['opers']:
							my_maa.recruit_log += oper['name'] + ' '
					my_maa.recruit_log += '\n'
		elif what == 'RecruitNoPermit':
			my_maa.recruit_log += f"公招无招聘许可\n"
		elif what == 'RecruitTagsSelected':
			my_maa.recruit_log += f"公招选中："
			my_maa.recruit_log += f"【 "
			for tag in js['details']['tags']:
				my_maa.recruit_log += f"{tag} "
			my_maa.recruit_log += f"】\n"
		elif what == 'NotEnoughStaff':
			my_maa.infrast_log += f"{facility_map[js['details']['facility']]}可用干员不足\n"
		elif what == 'UseMedicine':
			my_maa.fight_log['log'] += f"使用{'即将过期' if js['details']['is_expiring'] else ''}理智药{js['details']['count']}个\n"
		elif what == 'SanityBeforeStage':
			my_maa.fight_log['sanity'] = f"剩余理智 {js['details']['current_sanity']}/{js['details']['max_sanity']}"
		
	if 'details' in js:
		if 'task' in js['details']:
			if js['details']['task'] == "StoneConfirm" and m == Message.SubTaskCompleted:
				my_maa.fight_log['log'] += "确认碎石一次\n"
			if js['details']['task'] == "InfrastDormDoubleConfirmButton":
				my_maa.infrast_log += "基建宿舍出现干员冲突，请检查\n"
    
	if my_maa.asst_config['python']['debug']:
		lg.info(m)
		lg.info(js)



class MAA:
	def __init__(self) -> None:
		self.connect_log = ''
		self.fight_log = {'stages':{},'drops':{},'msg':'','log':'','stages':'','sanity':''}	#作战信息
		self.recruit_log = ''
		self.infrast_log = ''
		self.running_config = ''
		self.stop_tag = '正常'	#任务运行完成后会检查回调函数有没有给出报错，有的话重新执行
		#MAA核心路径
		self.core_path = Path(__file__).parent.parent.parent / "MAA-linux"
		os.environ['LD_LIBRARY_PATH'] = str(self.core_path)
		#获取maa自定义配置
		self.asst_config_path = str(Path(__file__).parent.parent / "config/asst.yaml")
		with open(self.asst_config_path, 'r', encoding='utf8') as config_f:
			self.asst_config = yaml.safe_load(config_f)
		#更新并加载核心和共享库
		self.update_and_load()
		self.clean_adb()
  




	def update_and_load(self, force=False):
		#更新版本
		lg.info("进入版本更新与加载函数")
		if self.asst_config['python']['auto_update'] or force:
			lg.info("开始更新")
			do_updated,self.update_log = Updater(self.core_path, Version.Beta).update()
			status = "LATEST"
			if do_updated:
				status = "UPDATED"
			recall = {
						"status": status,
						"payload": self.update_log.rstrip(),
						"type": "update_notice",
					}
			global_var.get("send_msg_waiting_queue").put(recall)
			lg.info("更新结束")
			if do_updated:
				lg.info("核心文件版本已有变化，目前尚无法实现热重载，即将退出Python进程，等待外部重启")
				time.sleep(5)
				save_cache()
				os._exit(1)
		else:
			lg.info("未开启自动更新")
		#添加自定义任务模块
		self.add_custom()
		lg.info("添加自定义任务模块结束")
		#加载资源
		Asst.load(path=self.core_path, incremental_path=self.core_path / 'cache')
		lg.info("加载资源结束")
		#构造并设置回调函数
		self.asst = Asst(callback=my_callback)
		lg.info("构造结束")
		#设置触控方式
		self.asst.set_instance_option(InstanceOptionType.touch_type, self.asst_config['instance_options']['touch_mode'])
		lg.info("加载完成")

	def add_custom(self):
		"""
		将自定义的任务动作和修复问题的模板图片合并到官方的文件中
		"""
		custom_tasks_path = Path(__file__).parent.parent / "custom/tasks.json"
		official_tasks_path = self.core_path / "resource/tasks.json"

		with open(custom_tasks_path, 'r', encoding='utf8') as file:
			customs_tasks = json.load(file)	#读取自定义任务动作
		with open(official_tasks_path, 'r', encoding='utf8') as file:
			official_tasks = json.load(file)	#读取官方任务动作
		for key, values in customs_tasks.items():
			official_tasks[key] = values	##自定义任务动作加入到官方配置并保存
		with open(official_tasks_path, 'w',encoding='utf8') as file:
			file.write(json.dumps(official_tasks, ensure_ascii=False, indent=4, separators=(', ', ': ')))

		custom_template_path = Path(__file__).parent.parent / "custom/template"
		official_template_path = self.core_path / "resource/template"
		custom_template = os.listdir(custom_template_path) 
		for template in custom_template: 
			custom_template_file_path = os.path.join(custom_template_path, template) 
			official_template_file_path = os.path.join(official_template_path, template) 
			with open(custom_template_file_path, 'rb') as custom_f: 
				with open(official_template_file_path, 'wb') as official_f: 
						official_f.write(custom_f.read())

	def clean_adb(self):
		try:
				cmd = f"ps -ef | grep {self.asst_config['connection']['adb']} | grep -v grep | awk '{{print $2}}' | xargs kill -9"
				with subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True,close_fds=True) as p:
					out, err = p.communicate(timeout=60)
		except subprocess.TimeoutExpired as e:
			lg.exception("发生subprocess.TimeoutExpired错误，准备重启")
			time.sleep(5)
			save_cache()
			os._exit(1)
		except OSError as e:
			lg.exception("发生系统错误，准备重启")
			time.sleep(5)
			save_cache()
			os._exit(1)
	def find_adb_wifi_port(self,retry=50):
		"""
		Android 11以上可以在开发人员选项内开启无线调试
		但是端口隔一段时间会变化，所以要扫描一下
		"""
		try:
			while retry:
				cmd = f'nmap {self.asst_config["connection"]["ip"]} -p 30000-49999 | awk "/\\/tcp/" | cut -d/ -f1'
				with subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True,close_fds=True) as p:
					out, err = p.communicate(timeout=60)
				port = out.decode('utf8').replace(' ','').replace('\n','')
				text = f"扫描得到ADB端口为：{port}"
				lg.info(text)
				if not port:
					text = "扫描不到设备ADB端口，等待重试"
					lg.error(text)
					time.sleep(5)
					retry -=1
				else:
					self.asst_config["connection"]["port"] = int(port)
					return int(port)
			text = "扫描不到设备ADB端口，不再重试，请排查"
			lg.error(text)
			return 0
		except subprocess.TimeoutExpired as e:
			lg.exception("发生subprocess.TimeoutExpired错误，准备重启")
			time.sleep(5)
			save_cache()
			os._exit(1)
		except OSError as e:
			lg.exception("发生系统错误，准备重启")
			time.sleep(5)
			save_cache()
			os._exit(1)
	def connect_adb(self):
		try:
			if not self.find_adb_wifi_port():
				return False
			cmd = f'{self.asst_config["connection"]["adb"]} connect {self.asst_config["connection"]["ip"]}:{self.asst_config["connection"]["port"]}'
			with subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True,close_fds=True) as p:
				out, err = p.communicate(timeout=60)
			result = out.decode('utf8').replace(' ','').replace('\n','')
			lg.info(f"ADB连接结果{result}")
			if "already" in result or 'connected' in result:
				return True
			return False
		except subprocess.TimeoutExpired as e:
			lg.exception("发生subprocess.TimeoutExpired错误，准备重启")
			time.sleep(5)
			save_cache()
			os._exit(1)
		except OSError as e:
			lg.exception("发生系统错误，准备重启")
			time.sleep(5)
			save_cache()
			os._exit(1)
	def connect(self, init=False, retry=0):
		"""
		通过ADB连接到安卓设备
		"""
		self.connect_log = f"第{retry}次尝试连接ADB"
		#获取ADB端口
		if ( init or retry ) and self.asst_config['connection']['scan_port']:
			if not self.find_adb_wifi_port():
				return False
		text = f'尝试连接到：{self.asst_config["connection"]["ip"]}:{self.asst_config["connection"]["port"]}'
		lg.info(text)
		self.connect_log += "\n" + text

		if self.asst.connect(	adb_path = self.asst_config["connection"]["adb"], 
								address = f'{self.asst_config["connection"]["ip"]}:{self.asst_config["connection"]["port"]}', 
								config = self.asst_config["connection"]["config"]
							):
			text = '连接成功'
			lg.info(text)
			self.connect_log += '\n' + text
			self.screenshot('连接成功后')
			return True
		else:
			if retry<10:
				text = f'连接失败，即将尝试重连'
				lg.error(text)
				return self.connect(retry=retry+1)
			else:
				text = f'连接失败，请检查MAA-CORE的日志，应当位于 {self.core_path}/debug/asst.log'
				lg.error(text)
				self.connect_log += text + '\n'
				return False

	def screenshot(self,file_name,rb=False): 
		"""
		调用MAA-CORE的API获取截图
		get_img这个不是立即截图，只是获取任务运行的最近一张截图，
		所以手动调用adb立即截图
		:params:
			``file_name``: 截图保存的文件名
			``rb``:  是否返回图片文件的二进制bytes数组
		:return: 图片文件bytes[] | None
		"""
		# async_call_id = self.asst.screenshot()
		# lg.info(f"将async_call_id：{async_call_id}加入到waiting_async队列中并等待")
		# self.waiting_async.append(async_call_id)
		# while async_call_id in self.waiting_async:
		# 	time.sleep(0)
		# lg.info(f"waiting_async结束，截图已完成")
		
		# img,length = self.asst.get_img()
		try:
			img_path = str(Path(__file__).parent.parent / f"img/{file_name}.png")
			shell_cmd = f'{self.asst_config["connection"]["adb"]} -s '\
						f'{self.asst_config["connection"]["ip"]}:{self.asst_config["connection"]["port"]} '\
						f'exec-out screencap -p > '\
						f'{img_path}'
			with subprocess.Popen(shell_cmd, stdout=subprocess.PIPE, shell=True,close_fds=True) as p:
				out, err = p.communicate(timeout=60)
			with open(img_path, 'rb') as f:
				img = f.read()
			length = len(img)
			lg.info(f"截图大小{length/1024}KBytes")
			if rb:
				return img
			else:
				return length
		except subprocess.TimeoutExpired as e:
			lg.exception("发生subprocess.TimeoutExpired错误，准备重启")
			time.sleep(5)
			save_cache()
			os._exit(1)
		except OSError as e:
			lg.exception("发生系统错误，准备重启")
			time.sleep(5)
			save_cache()
			os._exit(1)


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

	def parse_logic(self, operator,cond) -> bool:
		lg.info(f"检查逻辑条件：{operator}")
		lg.info(cond)
		if operator == 'not':
			tmp_bool = self.parse_logic(list(cond.keys())[0], list(cond.values())[0])
			if not tmp_bool:
				lg.info("not 条件检查通过")
				return True
			else:
				lg.info("not 条件检查不通过")
				return False
		if operator == 'and':
			for sub_cond in cond:
				if not self.parse_logic(list(sub_cond.keys())[0], list(sub_cond.values())[0]):
					lg.info("and 条件检查不通过")
					return False
				else:
					lg.info("and 条件检查部分通过")
			lg.info("and 条件检查部分通过")
			return True
		if operator == 'or':
			for sub_cond in cond:
				if self.parse_logic(list(sub_cond.keys())[0], list(sub_cond.values())[0]):
					lg.info("or 条件检查通过")
					return True
				else:
					lg.info("or 条件检查部分不通过")
			lg.info("or 条件检查不通过")
			return False
		if operator == 'id':
			if cond in self.config_success_fight_id:
				lg.info("任务有效性检查通过")
				return True
			else:
				lg.info("任务有效性检查不通过")
				return False

	def parse_condition(self,cond:dict):
		lg.info("检查任务是否符合启用条件")
		enable = True
		now = datetime.datetime.now()
		for key, value in cond.items():
			if key == 'weekday':
				lg.info(f"检查星期序号，当前为{now.weekday()+1}")
				if now.weekday()+1 not in value:
					lg.info("未达到该任务启用的星期范围，跳过")
					enable = False
					break
				lg.info("当前时间在该任务启用的星期范围内，通过条件检查")
			elif key == 'hour':
				lg.info(f"检查时间段，当前为{now.hour}时")
				if '<' in value and  now.hour >= value['<']:
					lg.info("时刻超过任务启用的范围，跳过")
					enable = False
					break
				if '>' in value and  now.hour <= value['>']:
					lg.info("时刻未达任务启用的范围，跳过")
					enable = False
					break
				lg.info("当前时间在该任务启用的时段范围内，通过条件检查")
			else:
				lg.info(f"检查逻辑条件")
				if not self.parse_logic(key,value):
					enable = False
					break
		return enable

	def interrupt_tasks_handler(self, data:dict):
		config_name = data['name'] if 'name' in data else int(time.time())
		lg.info(f"正在运行中断任务配置：{config_name}")
		currentDateAndTime = datetime.datetime.now()
		currentTime = currentDateAndTime.strftime("%Y-%m-%d %H:%M:%S")
		recall = {
					"payload": f"{currentTime}\n开始运行中断配置：{config_name}",
					"status": "BEGIN",
					"type": "interrupt_config_notice",
				}
		global_var.get("send_msg_waiting_queue").put(recall)
		task_index = 0
		while task_index < len(data['tasks']):
			task_begin_time = time.time()
			lg.info(f"正在处理第{task_index}个中断任务")
			task = data['tasks'][task_index]
			if 'id' not in task:
				task['id'] = f"{task['type']}_{task_index}"
			lg.info(task)
			recall = {
						"devices": uuid.UUID(int = uuid.getnode()).hex[-12:].upper(),
						"user": "",
						"task": task['id'],
						"task_type": task['type'],
						"status": "SUCCESS",
						"payload": "",
						"image": "",
						"type": "interrupt_task_report",
						"name": config_name,
						"task_config": task
					}
			task_index += 1
			if task['type'] == 'Screenshot':
				img_msg = self.screenshot(f"Interrupt_{recall['task']}",rb=True)
				if len(img_msg) < 10*1024:
					time.sleep(10)
					text = f"截图数据大小异常（{round(len(img_msg)/1024,2)}KBytes）KBytes，尝试重连ADB"
					lg.error(text)
					recall['payload'] = text
					if not self.connect_adb():
						text = "\n重连失败，请排查错误"
						lg.error(text)
						recall['payload'] = text
					else:
						
						img_msg = self.screenshot(f"Interrupt_{recall['task']}",rb=True)
						if len(img_msg) < 10*1024:
							text = f"\n截图数据异常（{round(len(img_msg)/1024,2)}KBytes）且重连无效，请排查错误"
							lg.error(text)
							recall['payload'] = text
						else:
							recall['image'] = base64.b64encode(img_msg).decode("utf-8")
				else:
					recall['image'] = base64.b64encode(img_msg).decode("utf-8")
				
			if task['type'] == 'Stop_config':
				if "params" in task and "name" in task['params'] and task['params']["name"] != "" and self.running_config != task['params']["name"]:
						lg.info("准备清除一份尚未运行的配置")
						cleaned = False
						for index in range((global_var.get("tasks_config_waiting_queue").qsize)):
							if global_var.get("tasks_config_waiting_queue").queue[index]['data']["name"] == task['params']["name"]:
								global_var.get("tasks_config_waiting_queue").queue.remove(global_var.get("tasks_config_waiting_queue").queue[index])
								lg.info(f"清除队列中排序为{index}的配置")
								cleaned = True
								recall['payload'] = f"已清除队列中等待运行的配置：{task['params']['name']}"
						if not cleaned:
							recall['payload'] = f"队列中没有名为{task['params']['name']}的配置"
							
				lg.info("停止maa当前任务并设置标记：跳过当前配置")
				self.stop_tag = '跳过当前配置'
				self.asst.stop()
				recall['payload'] = "已下发终止当前配置指令"
			if task['type'] == 'Stop':
				lg.info("停止maa当前任务并设置标记：停止所有配置")
				self.stop_tag = '停止所有配置'
				global_var.set("clean_all_config_tag", True)
				self.asst.stop()
				recall['payload'] = "已下发终止所有配置指令"
			lg.info("发送回调消息")
			recall['duration'] = int(time.time()-task_begin_time)
			global_var.get("send_msg_waiting_queue").put(recall)
		currentDateAndTime = datetime.datetime.now()
		currentTime = currentDateAndTime.strftime("%Y-%m-%d %H:%M:%S")
		recall = {
					"payload": f"{currentTime}\n运行结束：{config_name}",
					"status": "END",
					"type": "interrupt_config_notice",
				}
		global_var.get("send_msg_waiting_queue").put(recall)


	def tasks_handler(self, data: dict):
		config_name = data['name'] if 'name' in data else int(time.time())
		lg.info(f"正在运行配置：{config_name}")
		self.running_config = config_name
		currentDateAndTime = datetime.datetime.now()
		currentTime = currentDateAndTime.strftime("%Y-%m-%d %H:%M:%S")
		recall = {
					"payload": f"{currentTime}\n开始运行配置：{config_name}",
					"status": "BEGIN",
					"type": "normal_config_notice",
				}
		global_var.get("send_msg_waiting_queue").put(recall)
		task_index = 0
		retry = 0
		success_tasks = []
		self.config_success_fight_id = []
		self.recruit_log = ''
		self.infrast_log = ''
		while task_index < len(data['tasks']):
			task_begin_time = time.time()
			lg.info(f"正在处理第{task_index}个任务")
			task = data['tasks'][task_index]
			if 'id' not in task:
				task['id'] = f"{task['type']}_{task_index}"
			lg.info(task)
			recall = {
						"devices": uuid.UUID(int = uuid.getnode()).hex[-12:].upper(),
						"user": "",
						"task": task['id'],
						"task_type": task['type'],
						"status": "SUCCESS",
						"payload": "",
						"image": "",
						"type": "normal_task_report",
						"name": config_name,
						"task_config": task

					}
			task_index += 1
			self.fight_log = {'stages':{},'drops':{},'msg':'','log':'','sanity':''}	#作战信息
			if task['type'] == 'Update':
				lg.info("收到更新任务，调用更新和加载函数")
				self.update_and_load(force=True)
				recall['duration'] = int(time.time()-task_begin_time)
				recall['payload'] = self.update_log
				# send_msg_waiting_queue.put(recall)
			else:
				lg.info("当前已执行了的核心任务")
				lg.info(success_tasks)
				if task_index-1 in success_tasks:
					# if task_index-1 != success_tasks[-1]:
						lg.info("跳过已执行了的任务")
						continue
				lg.info("检查任务是否启用")
				if 'enable' in task and task['enable'] == False:
					lg.info("该任务未启用，跳过")
					continue
				if 'condition' in task:
					if not self.parse_condition(task['condition']):
						lg.info("任务条件检查未通过，跳过当前任务")
						continue
				lg.info("检查完毕：任务正常启用")
				lg.info("运行任务前检查ADB连接情况")
				if not self.connect():
					lg.error("连接失败，放弃该配置的运行")
					recall['status'] = "FAILED"
					recall['payload'] = self.connect_log
					recall['duration'] = int(time.time()-task_begin_time)
					global_var.get("send_msg_waiting_queue").put(recall)
					break
				lg.info("检查完毕：ADB连接正常")

				lg.info("准备提交任务")
				if "params" in task:
					self.asst.append_task(task['type'], task['params'])
				else:
					self.asst.append_task(task['type'])
				lg.info("检查是否需要在运行前截图")
				img_msg = None
				if ("screenshot" in task and (task['screenshot'] == 'before' or task['screenshot'] =='both')):
					img_msg = self.screenshot(f"before_{recall['task']}",rb=True)
				lg.info("启动运行")
				self.asst.start()
				lg.info("循环等待任务结束")
				while self.asst.running():
					time.sleep(0)
				lg.info("任务结束运行")
				lg.info(f"检查结束标记：{self.stop_tag}")
				if self.stop_tag == 'MAA出错':
					text = f"任务运行过程中存在出错情况，具体问题定位有待代码完善"
					recall['payload'] += text + '\n'
					# self.error_count +=1
					# if self.error_count >= self.error_threshold: 
					# 	text = "出错次数超过阈值，退出程序"
					# 	lg.error(text)
					# 	send_msg(text)
					# 	exit(1)
					# else:
					# 	text = f"MAA出错，尝试重新回到第{latest_official_task_count}个任务{task_config['tasks'][latest_official_task_count]['type']}"
					# 	lg.error(text)
					# 	task_count = 0
					# 	self.stop_tag = '正常'
				if '剿灭' in task['id']:
					self.fight_log['log'] += '目前MAA剿灭功能与结果统计不完善\n'
					
				recall['payload'] += self.fight_log['msg']
				if self.fight_log['log']:
					recall['payload'] += "\n" + self.fight_log['log']
				if self.fight_log['sanity']:
					recall['payload'] += "\n" + self.fight_log['sanity']
				if len(self.fight_log['stages']) > 0:
					self.config_success_fight_id.append(task['id'])
				lg.info("现在成功有效执行了的Fight任务有：")
				lg.info(self.config_success_fight_id)
    
				if task['type'] == 'Recruit' and self.recruit_log:
					if recall['payload']:
						recall['payload'] += '\n'
					recall['payload'] += self.recruit_log 
				if '公招' in task['id'] and self.recruit_log:
					if recall['payload']:
						recall['payload'] += '\n'
					recall['payload'] += self.recruit_log 

				if task['type'] == 'Infrast' and self.infrast_log:
					if recall['payload']:
						recall['payload'] += '\n'
					recall['payload'] += self.infrast_log 

				# if self.stop_tag == '手动结束':
				# 	text = "收到手动结束任务指令，退出当前任务配置"
				# 	lg.error(text)
				# 	if recall['payload']:
				# 		recall['payload'] += '\n'
				# 	recall['payload'] += text
				# 	self.stop_tag = '正常'
				# 	recall['payload'] += text
				# 	recall['status'] = "FAILED"
				# 	recall['duration'] = int(time.time()-task_begin_time)
				# 	global_var.get("send_msg_waiting_queue").put(recall)
				# 	return 
				if self.stop_tag == '任务链出错':
					if retry < 2:
						retry += 1
						self.stop_tag = '正常'
						text = "任务运行过程出错，尝试重新执行该配置一次"
						lg.error(text)
						if recall['payload']:
							recall['payload'] += '\n'
						recall['payload'] += text 
						recall['status'] = "FAILED"
						recall['duration'] = int(time.time()-task_begin_time)
						# global_var.get("send_msg_waiting_queue").put(recall)
						task_index = 0
						self.asst.stop()
						continue
					else:
						self.stop_tag = '正常'
						text = "任务运行过程出错且重试失败，放弃该任务"
						lg.error(text)
						if recall['payload']:
							recall['payload'] += '\n'
						recall['payload'] += text 
						recall['status'] = "FAILED"
						recall['duration'] = int(time.time()-task_begin_time)
						global_var.get("send_msg_waiting_queue").put(recall)
						self.asst.stop()
						continue
				if self.stop_tag == '需要重连':
					text = "任务运行过程出错，重新尝试连接到adb"
					lg.error(text)
					if recall['payload']:
						recall['payload'] += '\n'
					recall['payload'] += text + '\n'
					if not self.connect(init=True):
						text = "连接失败，放弃该配置的运行"
						lg.error(text)
						recall['status'] = "False"
						recall['payload'] += self.connect_log + "\n" + text
						recall['duration'] = int(time.time()-task_begin_time)
						global_var.get("send_msg_waiting_queue").put(recall)
						break
					self.stop_tag = '正常'
					task_index = 0
					text = f"MAA重连成功，尝试重新执行未完成的任务"
					lg.error(text)
					recall['payload'] += text
					recall['status'] = "FAILED"
					recall['duration'] = int(time.time()-task_begin_time)
					global_var.get("send_msg_waiting_queue").put(recall)
					self.asst.stop()
					continue
				
				lg.info("检查是否需要在运行后截图")
				if "screenshot" in task and (task['screenshot'] == 'after' or task['screenshot'] =='both'):
					img_msg = self.screenshot(f"after_{recall['task']}",rb=True)

				if task['type'] != 'Custom' and task['type'] != 'CloseDown' and task['type'] != 'StartUp':
					success_tasks.append(task_index-1)
					text = f"更新最近一个已完成的非custom非启闭任务为：{recall['task']}，序号为{task_index-1}"
					lg.info(text)
					lg.info(success_tasks)
				if img_msg:
					lg.info("将截图填入回调消息中")
					recall['image'] = base64.b64encode(img_msg).decode("utf-8")

				if self.stop_tag == '跳过当前配置':
					self.stop_tag = '正常'
					text = "收到指令，终止当前配置运行"
					lg.error(text)
					if recall['payload']:
						recall['payload'] += '\n'
					recall['payload'] += text 
					recall['duration'] = int(time.time()-task_begin_time)
					global_var.get("send_msg_waiting_queue").put(recall)
					self.asst.stop()
					break
				if self.stop_tag == '停止所有配置':
					self.stop_tag = '正常'
					text = "收到指令，终止所有配置运行"
					lg.error(text)
					if recall['payload']:
						recall['payload'] += '\n'
					recall['payload'] += text 
					recall['duration'] = int(time.time()-task_begin_time)
					global_var.get("send_msg_waiting_queue").put(recall)
					self.asst.stop()
					break
				lg.info("发送回调消息")
				recall['duration'] = int(time.time()-task_begin_time)
				global_var.get("send_msg_waiting_queue").put(recall)

				lg.info("清理任务队列，等待后续任务执行")
				retry = 0
				self.asst.stop()
		currentDateAndTime = datetime.datetime.now()
		currentTime = currentDateAndTime.strftime("%Y-%m-%d %H:%M:%S")
		recall = {
					"payload": f"{currentTime}\n运行结束：{config_name}",
					"status": "END",
					"type": "normal_config_notice",
				}
		global_var.get("send_msg_waiting_queue").put(recall)
		


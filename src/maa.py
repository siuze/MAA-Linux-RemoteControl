import base64
from collections import deque
import datetime
import json
import os
import signal
import subprocess
import time
from typing import Any, Literal, TypedDict
from pathlib import Path

import yaml
from .asst.asst import Asst
from .asst.updater import Updater
from .asst.utils import InstanceOptionType, Message, Version
from loguru import logger as lg
from multiprocessing.queues import Queue as QUEUE
from src._global import Notice, TaskCondition, TaskConfig, Task, facility_translate
from src import check_oops, cache
from functools import cache as CACHE

class FightLog(TypedDict):
	stages: dict[str, int]
	drops: dict[str, int]
	stages_drops_msg: str
	other_msg:str
	sanity: str

class RuningLog(TypedDict):
	connect: str
	fight: FightLog
	recruit: str
	infrast: str
	OperBox: str
	important: str

@Asst.CallBackType
def my_callback(msg: int, details: bytes, arg: Any) -> None:
	"""
	MAA-CORE的运行消息回调函数
	:params:
			``msg``: 消息类型
			``details``:  消息具体内容
	:return: None
	"""

	消息类型 = Message(msg)
	json消息内容 = json.loads(details.decode("utf-8"))
	self = MAA()
	if 消息类型 in (Message.InternalError, Message.SubTaskError, Message.TaskChainError):
		lg.error(f"MAA出错：{str(消息类型)} {json消息内容}")
	if 消息类型 == Message.TaskChainError and json消息内容['taskchain'] not in ('Custom',):
		self.任务执行结果.append("任务链出错")
		self.maa.stop()
	elif 消息类型 == Message.SubTaskError:
		if "first" in json消息内容 and json消息内容["first"][0] == "FightBegin":
			self.任务执行结果.append("作战启动检查异常")
			self.maa.stop()
		if "subtask" in json消息内容 and json消息内容["subtask"] == "StageNavigationTask":
			self.任务执行结果.append("关卡导航异常")
			self.maa.stop()
	elif 消息类型 == Message.AsyncCallInfo:
		text = f"收到异步调用的回调消息：{str(消息类型)} {details.decode('utf-8')}"
		# maa.waiting_async.remove(js['async_call_id'])
		lg.info(text)

	if "what" in json消息内容:
		what = json消息内容["what"]
		if what == "UuidGot":
			text = f"获取到ADB设备uuid：{json消息内容['details']['uuid']}"
			lg.info(text)
			self.运行日志["connect"] += text + "\n"
		elif what == "ResolutionGot":
			text = f"获取到ADB设备分辨率：{json消息内容['details']['height']} X {json消息内容['details']['width']}"
			lg.info(text)
			self.运行日志["connect"] += text + "\n"
		elif what == "StageDrops":
			self.更新作战结果日志(json消息内容["details"])
		elif what == "ScreencapFailed" and "需要重连" not in self.任务执行结果:
			text = "获取截图失败，可能是ADB配置出现问题或Android 11无线调试变化了端口，尝试重新连接"
			lg.info(text)
			self.任务执行结果.append("需要重连")
			self.maa.stop()
		elif what == "RecruitSpecialTag":
			self.运行日志["recruit"] += f"!重要!  识别到稀有标签：【{json消息内容['details']['tag']}】\n"
		elif what == "RecruitResult":
			if json消息内容["details"]["level"] >= 5:
				self.运行日志["recruit"] += "!重要!  存在五星或六星的公招标签组合，请在任务结束后检查：\n"
				result = json消息内容["details"]["result"]
				for match in result:
					if match["level"] >= 5:
						tags = "【 "
						for tag in match["tags"]:
							tags += tag + " "
						tags += "】"
						self.运行日志["recruit"] += tags
						for oper in match["opers"]:
							self.运行日志["recruit"] += oper["name"] + " "
					self.运行日志["recruit"] += "\n"
		elif what == "RecruitNoPermit":
			self.运行日志["recruit"] += "公招无招聘许可\n"
		elif what == "RecruitTagsSelected":
			self.运行日志["recruit"] += "公招选中："
			self.运行日志["recruit"] += "【 "
			for tag in json消息内容["details"]["tags"]:
				self.运行日志["recruit"] += f"{tag} "
			self.运行日志["recruit"] += "】\n"
		elif what == "NotEnoughStaff":
			self.运行日志["infrast"] += f"{facility_translate[json消息内容['details']['facility']]}可用干员不足\n"
		elif what == "InfrastTrainingCompleted":
			self.运行日志["infrast"] += f"!重要! 干员【{json消息内容['details']['operator']}】的技能【{json消息内容['details']['skill']}】专精【{json消息内容['details']['level']}】训练完成\n"
		elif what == "UseMedicine":
			text = f"使用{'即将过期' if json消息内容['details']['is_expiring'] else ''}理智药{json消息内容['details']['count']}个\n"
			self.运行日志["fight"]['other_msg'] += text
			self.运行日志["important"] += text
		elif what == "SanityBeforeStage":
			self.运行日志["fight"]["sanity"] = f"剩余理智 {json消息内容['details']['current_sanity']}/{json消息内容['details']['max_sanity']}"
		elif what == "OperBoxInfo":
			if json消息内容["details"]['done']:
				text = '尚未获得的干员：'
				own: list[str]  = []
				not_own: list[str] = []
				for it in json消息内容['details']['all_opers']:
					if it['own'] is False:
						if it['name'].startswith('预备干员'):
							continue
						if it['name'] in ('Misery', '郁金香', 'Pith', 'Sharp', '阿米娅-WARRIOR', '阿米娅-MEDIC', 'Touch', 'Raidian', 'Mechanist', 'Stormeye'):
							continue
						text += f'{it['name']}，'
						# print(f'{it['name']}, ',end='')
						not_own.append(it['name'])
					else:
						own.append(it['name'])
				if text[-1:] == '，':
					text = text[:-1]
				text += '\n（MAA干员识别功能尚不完善，可能出现错识别、漏识别的问题）'
				lg.info(own)
				lg.info(not_own)
				lg.info(text)
				self.运行日志['OperBox'] = text
		elif what == 'NotThreeStars':
			stage = ''
			if 'params' in self.正在处理的任务 and 'stage' in self.正在处理的任务['params']:
				stage = self.正在处理的任务['params']['stage']
			text = f"未能三星通关作战关卡{stage}，请在任务结束后检查代理是否稳定\n"
			self.运行日志["fight"]['other_msg'] += text
			self.运行日志["important"] += text


	if "details" in json消息内容:
		if "task" in json消息内容["details"]:
			if json消息内容["details"]["task"] == "StoneConfirm" and 消息类型 == Message.SubTaskCompleted:
				self.运行日志["fight"]['other_msg'] += "确认碎石一次\n"
			if json消息内容["details"]["task"] == "InfrastDormDoubleConfirmButton":
				self.运行日志["infrast"] += "基建宿舍出现干员冲突，请检查\n"

	if self.运行配置["python"]["debug"]:
		lg.info(消息类型)
		lg.info(json消息内容)

def format_time():
	currentDateAndTime = datetime.datetime.now()
	currentTime = currentDateAndTime.strftime("%Y-%m-%d %H:%M:%S")
	return currentTime


@CACHE
class MAA:
	__slots__ = (
		"待执行的一般配置队列",
		"待执行的中断配置队列",
		'待发送的消息队列',
		"正在处理的配置",
		"正在处理的任务",
		"已实际执行过的Fight任务name",
		"已启用的任务name",
		'作战任务阻塞标记',
		'任务执行结果',
		'MAA内核路径',
		'运行配置',
		'退出信号',
		'运行日志',
		'maa',
		'inited'
		)
	def init(self,待执行的一般配置队列: deque[TaskConfig],
				待执行的中断配置队列: deque[TaskConfig],
				待发送的消息队列: QUEUE[Notice],):
		self.inited = True
		self.待执行的一般配置队列 = 待执行的一般配置队列
		self.待执行的中断配置队列 = 待执行的中断配置队列
		self.待发送的消息队列 = 待发送的消息队列
		self.运行日志: RuningLog = {
			"connect": "", 
			"fight": {
				"stages": {}, 
				"drops": {}, 
				'other_msg': "", 
				'stages_drops_msg': "", 
				"sanity": ""}, 
			"recruit": "", 
			"infrast": "",
			'OperBox':'', 
			"important": ''}
		self.正在处理的配置: TaskConfig  # 当前正在运行的配置内容
		self.正在处理的任务: Task  # 当前正在运行的任务
		self.任务执行结果: list[Literal['正常','跳过当前配置','停止所有配置','MAA出错', '关卡导航异常', '作战启动检查异常','任务链出错','需要重连']] = ["正常"]  # 任务运行完成后会检查回调函数有没有给出报错标记，有的话会按照不同的标记进行处理
		self.作战任务阻塞标记:bool = False
		self.MAA内核路径 = Path(__file__).parent.parent.parent / "MAA-linux"  # MAA核心路径
		self.退出信号: bool = False
		with open(Path(__file__).parent.parent / "config.yaml", "r", encoding="utf8") as config_f:  # 获取maa自定义配置
			self.运行配置 = yaml.safe_load(config_f)
		self.更新并加载MAA核心和共享库()  # 更新并加载核心和共享库
		# self.clean_adb()  # 清理残留的adb进程
	def __init__(self,
				) -> None:
		self.inited = False
		pass






	def 重置运行日志(self):
		self.运行日志["connect"] = ''
		self.运行日志['fight']["stages"] = {}
		self.运行日志['fight']['drops'] = {}
		self.运行日志['fight']['other_msg'] = ''
		self.运行日志['fight']['stages_drops_msg'] = ''
		self.运行日志['important'] = ''
		self.运行日志['infrast'] = ''
		self.运行日志['recruit'] = ''
		self.运行日志['OperBox'] = ''

	def 启动子进程(self, cmd: str, timeout: float=30, skip: bool=False) -> bytes:
		"""
		执行linux命令,返回list
		:param cmd: linux命令
		:param timeout: 超时时间,生产环境, 特别卡, 因此要3秒
		:param skip: 是否跳过超时限制
		:return: bytes std输出的内容
		"""
		try:
			lg.info(f"发起子进程执行命令：{cmd}")
			p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, close_fds=True, preexec_fn=os.setsid)
			t_beginning = time.time()  # 开始时间
			while True:
				if p.poll() is not None:
					break
				seconds_passed = time.time() - t_beginning
				if not skip:
					if seconds_passed > timeout:
						lg.error(f"错误, 命令: {cmd} 执行超时!")
						try:
							os.killpg(p.pid, signal.SIGUSR1)
						except Exception:
							lg.exception("杀死超时进程时出错")
						os._exit(0)
			result = p.stdout.read()  # type: ignore # 结果输出
			return result
		except KeyboardInterrupt:
			lg.error("检测到KeyboardInterrupt，退出程序")
			os._exit(0)
		except subprocess.TimeoutExpired:
			lg.exception("发生subprocess.TimeoutExpired错误，退出程序")
			time.sleep(5)
			self.导出cache()
			os._exit(0)
		except OSError:
			lg.exception("发生系统错误，准备退出")
			time.sleep(5)
			self.导出cache()
			os._exit(0)
		except Exception:
			lg.exception("发生错误，准备退出")
			time.sleep(5)
			self.导出cache()
			os._exit(0)

	def 导出cache(self):
		cache.导出_cache(self.待执行的一般配置队列, self.待执行的中断配置队列)

	def 检查退出信号(self):
		if self.退出信号:
			lg.info("检查到退出标记，关闭MAA进程")
			os._exit(0)

	def 更新并加载MAA核心和共享库(self, force: bool=False):
		"""
		通过MAA连接到安卓设备
		:param:
		        `force`: bool=False 是否强制检查更新，为False的话会按照用户配置文件中的选择来
		:return: none
		"""
		self.检查退出信号()
		lg.info("进入版本更新与加载函数")
		proxies = None
		if "proxy" in self.运行配置["python"] and self.运行配置["python"]["proxy"]:
			proxies = {"http": self.运行配置["python"]["proxy"], "https": self.运行配置["python"]["proxy"]}

		if self.运行配置["python"]["auto_update"] or force:
			lg.info(f"开始更新 {self.MAA内核路径=}")
			已实际更新, 已实际OTA, 更新日志 = Updater(maa_内核路径=self.MAA内核路径, maa版本类型=Version.Beta, http代理=proxies).update()
			status = "OK"  # 默认已是最新无需更新
			if 已实际更新 or 已实际OTA:
				status = "SUCCESS"  # 已进行更新操作
			recall: Notice = {
				"status": status,
				"payload": 更新日志.rstrip(),
				"type": "update_log",
			}
			self.待发送的消息队列.put(recall)
			lg.info("更新结束")
			if status == 'SUCCESS':
				lg.info("核心文件版本已有变化，5s后退出当前Python MAA子进程，等待守护主进程重新发起子进程")
				self.导出cache()
				time.sleep(5)
				os._exit(0)
		else:
			lg.info("未开启自动更新")

		# 添加自定义任务模块
		self.添加自定义任务()
		lg.info("添加自定义任务模块结束")

		# 加载资源
		Asst.load(path=self.MAA内核路径, incremental_path=self.MAA内核路径 / "cache")
		lg.info("加载资源结束")

		# 构造并设置回调函数
		self.maa = Asst(callback=my_callback)
		lg.info("构造Asst并设置回调函数结束")

		# 设置触控方式
		self.maa.set_instance_option(InstanceOptionType.touch_type, self.运行配置["instance_options"]["touch_mode"])
		lg.info("加载完成")

	def 添加自定义任务(self):
		"""
		将自定义的任务动作和修复问题的模板图片合并到官方的文件中
		"""
		self.检查退出信号()
		custom_tasks_path = Path(__file__).parent.parent / "data/patch/tasks.json"
		official_tasks_path = self.MAA内核路径 / "resource/tasks.json"
		if os.path.exists(custom_tasks_path) and os.path.exists(official_tasks_path):
			with open(custom_tasks_path, "r", encoding="utf8") as file:
				customs_tasks = json.load(file)  # 读取自定义任务动作
			with open(official_tasks_path, "r", encoding="utf8") as file:
				official_tasks = json.load(file)  # 读取官方任务动作
			for key, values in customs_tasks.items():
				official_tasks[key] = values  ##自定义任务动作覆盖到官方配置并保存
			with open(official_tasks_path, "w", encoding="utf8") as file:
				file.write(json.dumps(official_tasks, ensure_ascii=False, indent=4, separators=(", ", ": ")))

		custom_template_path = Path(__file__).parent.parent / "data/patch/template"
		official_template_path = self.MAA内核路径 / "resource/template"
		if os.path.exists(custom_template_path) and os.path.exists(official_template_path):
			custom_template = os.listdir(custom_template_path)
			for template in custom_template:
				custom_template_file_path = os.path.join(custom_template_path, template)
				official_template_file_path = os.path.join(official_template_path, template)
				with open(custom_template_file_path, "rb") as custom_f:
					with open(official_template_file_path, "wb") as official_f:
						official_f.write(custom_f.read())

		custom_ota_tasks_path = Path(__file__).parent.parent / "data/patch/cache/resource/tasks.json"
		official_ota_tasks_path = self.MAA内核路径 / "cache/resource/tasks.json"
		if os.path.exists(custom_ota_tasks_path) and os.path.exists(official_ota_tasks_path):
			with open(custom_ota_tasks_path, "r", encoding="utf8") as file:
				customs_tasks = json.load(file)  # 读取自定义任务动作
			with open(official_ota_tasks_path, "r", encoding="utf8") as file:
				official_tasks = json.load(file)  # 读取官方任务动作
			for key, values in customs_tasks.items():
				official_tasks[key] = values  ##自定义任务动作覆盖到官方配置并保存
			with open(official_ota_tasks_path, "w", encoding="utf8") as file:
				file.write(json.dumps(official_tasks, ensure_ascii=False, indent=4, separators=(", ", ": ")))

	def clean_adb(self):
		"""
		清理残留的ADB进程
		:param: none
		:return: none
		"""
		try:
			self.检查退出信号()
			cmd = f"ps -ef | grep {self.运行配置['connection']['adb']} | grep -v grep | awk '{{print $2}}' | xargs kill -9"
			self.启动子进程(cmd)
		except Exception:
			lg.exception("clean_adb 发生错误，准备重启")
			time.sleep(5)
			self.导出cache()
			os._exit(0)

	def find_adb_wifi_port(self, retry: int=50):
		"""
		Android 11以上可以在开发人员选项内开启无线调试
		但是端口隔一段时间会变化，所以要扫描一下
		"""
		try:
			while retry:
				self.检查退出信号()
				cmd = f'nmap {self.运行配置["connection"]["ip"]} -p 30000-49999 | awk "/\\/tcp/" | cut -d/ -f1'
				out = self.启动子进程(cmd=cmd)
				port = out.decode("utf8").replace(" ", "").replace("\n", "")
				text = f"扫描得到ADB端口为：{port}"
				lg.info(text)
				if not port:
					text = "扫描不到设备ADB端口，等待5s重试"
					lg.error(text)
					time.sleep(5)
					retry -= 1
				else:
					self.运行配置["connection"]["port"] = int(port)
					return int(port)
			text = "扫描不到设备ADB端口，不再重试，请排查"
			lg.error(text)
			return 0
		except Exception:
			lg.exception("find_adb_wifi_port发生错误，准备重启")
			time.sleep(5)
			self.导出cache()
			os._exit(0)

	def connect_adb(self):
		"""
		通过ADB直接连接到安卓设备（不经过maa）
		param: None
		return: bool 是否连接成功
		"""
		try:
			self.检查退出信号()
			if self.运行配置["connection"]["scan_port"] and not self.find_adb_wifi_port():
				return False
			cmd = f'{self.运行配置["connection"]["adb"]} connect {self.运行配置["connection"]["ip"]}:{self.运行配置["connection"]["port"]}'
			out = self.启动子进程(cmd=cmd)
			result = out.decode("utf8").replace(" ", "").replace("\n", "")
			lg.info(f"ADB连接结果：{result}")
			if "already" in result or "connected" in result:
				return True
			return False
		except Exception:
			lg.exception("connect_adb发生错误，准备重启")
			time.sleep(5)
			self.导出cache()
			os._exit(0)

	def connect(self, init: bool=False, retry: int=0) -> bool:
		"""
		通过MAA连接到安卓设备
		:param:
		        `init`: bool=False 是否重新扫描端口
		        `retry`: int=0 当前已重试次数
		:return: bool 是否连接成功
		"""
		self.检查退出信号()

		if self.maa.connected():
			text = "MAA当前已经通过ADB连接到安卓设备了，不需要重新连接"
			lg.info(text)
			self.运行日志["connect"] = text
			return True

		text = f"第{retry}次尝试连接ADB"
		self.运行日志["connect"] = text
		lg.info(text)

		# 获取ADB端口
		if (init or retry) and self.运行配置["connection"]["scan_port"]:
			if not self.find_adb_wifi_port():
				return False

		text = f'尝试连接到：{self.运行配置["connection"]["ip"]}:{self.运行配置["connection"]["port"]}'
		lg.info(text)
		self.运行日志["connect"] += "\n" + text

		self.connect_adb()
		if self.maa.connect(adb_path=self.运行配置["connection"]["adb"], address=f'{self.运行配置["connection"]["ip"]}:{self.运行配置["connection"]["port"]}', config=self.运行配置["connection"]["config"]):
			text = "连接成功"
			lg.info(text)
			self.运行日志["connect"] += "\n" + text
			self.立即截图("连接成功后")
			return True
		else:
			if retry < 10:
				text = "连接失败，即将尝试重连"
				lg.error(text)
				return self.connect(retry=retry + 1)
			else:
				text = f"连接失败，请检查MAA-CORE的日志，应当位于 {self.MAA内核路径}/debug/asst.log"
				lg.error(text)
				self.运行日志["connect"] += text + "\n"
				return False

	def 立即截图(self, file_name: str,):
		"""
		MAA-CORE的API获取截图不是立即截图，只是获取任务运行的最近一张截图，
		所以手动使用adb立即截图
		:params:
		        ``file_name``: str  截图保存的文件名
		        ``rb``: bool=False  是否返回图片文件的二进制bytes数组
		:return: bytes[] | int 图片文件 | 图片大小
		"""
		try:
			self.检查退出信号()
			img_path = str(Path(__file__).parent.parent / f"data/img/{file_name}.png")
			shell_cmd = f'{self.运行配置["connection"]["adb"]} -s ' f'{self.运行配置["connection"]["ip"]}:{self.运行配置["connection"]["port"]} ' f'exec-out screencap -p > ' f'{img_path}'
			self.启动子进程(shell_cmd)
			with open(img_path, "rb") as f:
				img = f.read()
			length = len(img)
			lg.info(f"截图大小{length/1024}KBytes")
			return img
		except Exception:
			lg.exception("screenshot发生错误，准备重启")
			time.sleep(5)
			self.导出cache()
			os._exit(0)

	def 更新作战结果日志(self, detail: dict[str, Any]):
		"""
		对回调函数收到的作战结果进行解析
		:params:
		        ``details``:  消息具体内容
		:return: None
		"""
		self.检查退出信号()
		stage = detail["stage"]["stageCode"]
		if stage not in self.运行日志["fight"]["stages"]:
			self.运行日志["fight"]["stages"][stage] = 1
		else:
			self.运行日志["fight"]["stages"][stage] += 1
		for drop in detail["stats"]:
			self.运行日志["fight"]["drops"][drop["itemName"]] = drop["quantity"]

		self.运行日志["fight"]["stages_drops_msg"] = "作战结果：\n"
		for key, value in self.运行日志["fight"]["stages"].items():
			self.运行日志["fight"]["stages_drops_msg"] += f"  {key} * {value}\n"
		self.运行日志["fight"]["stages_drops_msg"] += "战斗掉落：\n"
		for key, value in self.运行日志["fight"]["drops"].items():
			self.运行日志["fight"]["stages_drops_msg"] += f"  {key} * {value}\n"
		while self.运行日志["fight"]["stages_drops_msg"][-1:] == "\n":
			self.运行日志["fight"]["stages_drops_msg"] = self.运行日志["fight"]["stages_drops_msg"][:-1]

	def 任务运行逻辑条件检查(self, operator: Literal['executed','enable', 'not', 'and', 'or'], cond: Any) -> bool:
		"""
		解析任务配置中的逻辑条件限制
		:params:
		        ``operator``: str 逻辑条件类型 "and" | "or" | "not" | "executed" | "enable"
		        ``cond``: 待判断内容
		:return: bool 条件检查是否通过
		"""
		self.检查退出信号()
		lg.info(f"检查逻辑条件：{operator}")
		lg.info(cond)
		if operator == "not":
			tmp_bool = self.任务运行逻辑条件检查(list(cond.keys())[0], list(cond.values())[0])
			if not tmp_bool:
				lg.info("not 条件检查通过")
				return True
			else:
				lg.info("not 条件检查不通过")
				return False
		if operator == "and":
			for sub_cond in cond:
				if not self.任务运行逻辑条件检查(list(sub_cond.keys())[0], list(sub_cond.values())[0]):
					lg.info("and 条件检查不通过")
					return False
				else:
					lg.info("and 条件检查部分通过")
			lg.info("and 条件检查全部通过")
			return True
		if operator == "or":
			for sub_cond in cond:
				if self.任务运行逻辑条件检查(list(sub_cond.keys())[0], list(sub_cond.values())[0]):
					lg.info("or 条件检查通过")
					return True
				else:
					lg.info("or 条件检查部分不通过")
			lg.info("or 条件检查不通过")
			return False
		if operator == "executed":
			if cond in self.已实际执行过的Fight任务name:
				lg.info("【战斗任务已实际执行过】检查项目通过")
				return True
			else:
				lg.info("【战斗任务已实际执行过】检查项目不通过")
				return False
		if operator == "enable":
			if cond in self.已启用的任务name:
				lg.info("【任务已启用】检查项目通过")
				return True
			else:
				lg.info("【任务已启用】检查项目不通过")
				return False

	def 任务运行条件检查(self, cond: TaskCondition):
		"""
		解析任务配置中的条件限制
		:params:
		        ``operator``: str 逻辑条件类型 "and" | "or" | "not" | "executed" | "enable"
		        ``cond``: dict 待判断内容
		:return: bool 条件检查是否通过，能否启用该任务
		"""
		self.检查退出信号()
		lg.info("检查任务是否符合启用条件")
		enable = True
		now = datetime.datetime.now()
		if "weekday" in cond:
			value = cond["weekday"]
			lg.info(f"检查星期序号，当前为{now.weekday()+1}")
			if now.weekday() + 1 not in value:
				lg.info("未达到该任务启用的星期范围，跳过")
				return False
			lg.info("当前时间在该任务启用的星期范围内，通过条件检查")
		if "hour" in cond:
			value = cond["hour"]
			lg.info(f"检查时间段，当前为{now.hour}时")
			if "<" in value and now.hour >= value["<"]:
				lg.info("时刻超过任务启用的范围，跳过")
				return False
			if ">" in value and now.hour <= value[">"]:
				lg.info("时刻未达任务启用的范围，跳过")
				return False
			lg.info("当前时间在该任务启用的时段范围内，通过条件检查")
		for key in ('not', 'and', 'or'):
			if key in cond:
				lg.info("检查逻辑条件")
				if not self.任务运行逻辑条件检查(key, cond[key]): # type: ignore
					return False
		return enable


	def 执行中断任务配置(self, config: TaskConfig):
		"""
		处理一条中断任务配置
		:params:
		        ``data``: dict 中断任务配置内容
		:return: none
		"""
		self.检查退出信号()
		lg.info(f"正在运行中断任务配置：{config['id']}")
		recall: Notice = {
			"payload": f"{format_time()}\n开始运行中断配置：{config['id']}",
			"status": "OK",
			"type": 'config_start',
			'config': self.生成回调消息中的配置信息(config, None)
			}
		self.待发送的消息队列.put(recall)
		task_index = 0
		while task_index < len(config["tasks"]):
			self.检查退出信号()
			lg.info(f"正在处理第{task_index}个中断任务")
			task = config["tasks"][task_index]
			lg.info(task)
			task_index += 1
			recall: Notice = {
				'type': 'task_result',
				'status': 'SUCCESS',
				"payload": '',
				"config": self.生成回调消息中的配置信息(config, task),
				"image": '',
				"duration": 0,
				}
			time_begin = time.perf_counter()
			if task["type"] == "Screenshot":
				img_msg = self.立即截图(f"Interrupt_{task['name']}")
				if len(img_msg) < 10 * 1024:
					time.sleep(10)
					text = f"截图数据大小异常（{round(len(img_msg)/1024,2)}KBytes），尝试重连ADB"
					lg.error(text)
					recall["payload"] = text
					if not self.connect_adb():
						text = "\n重连失败，请排查错误"
						lg.error(text)
						recall["payload"] = text
					else:
						img_msg = self.立即截图(f"Interrupt_{task['name']}")
						if len(img_msg) < 10 * 1024:
							text = f"\n截图数据异常（{round(len(img_msg)/1024,2)}KBytes）且重连无效，请排查错误"
							lg.error(text)
							recall["payload"] = text
						else:
							recall["image"] = base64.b64encode(img_msg).decode("utf-8")
				else:
					recall["image"] = base64.b64encode(img_msg).decode("utf-8")

			elif task["type"] == "Stop_config":
				if "params" in task:
					需要删除的配置名 = task["params"]["id"]
					if self.正在处理的配置['id'] != 需要删除的配置名:
						lg.info("准备清除一份尚未运行的配置")
						cleaned = False
						for _ in range(len(self.待执行的一般配置队列)):
							del_config = self.待执行的一般配置队列.popleft()
							if del_config["id"] != 需要删除的配置名:
								self.待执行的一般配置队列.append(del_config)
							else:
								lg.info(f"清除队列中一份配置：{需要删除的配置名}")
								cleaned = True
								recall["payload"] += f"已清除队列中一份尚未开始运行的配置：【{需要删除的配置名}】，其他配置正常运行"
						if not cleaned:
							recall["payload"] += f"队列中没有名为【{需要删除的配置名}】的配置"
					else:
						lg.info("停止maa当前任务并设置标记：跳过当前配置")
						self.任务执行结果.append("跳过当前配置")
						self.maa.stop()
						recall["payload"] += f"已下发指令：终止当前正在运行的配置【{需要删除的配置名}】"

			elif task["type"] == "Stop":
				lg.info("停止maa当前任务并设置标记：停止所有配置")
				self.任务执行结果.append("停止所有配置")
				self.待执行的一般配置队列.clear()
				self.maa.stop()
				recall["payload"] = "已下发指令：停止所有配置的运行"

			lg.info("发送回调消息")
			recall["duration"] = int(time.perf_counter() - time_begin)
			self.待发送的消息队列.put(recall)

		recall = {
			"payload": f"{format_time()}\n中断配置运行结束：{config['id']}",
			"status": "OK",
			"type": "config_end",
			'config': self.生成回调消息中的配置信息(config, None)
			}
		self.待发送的消息队列.put(recall)
		self.导出cache()

	def 执行一般任务配置(self, config: TaskConfig):
		self.检查退出信号()
		config_name = config["id"]
		lg.info(f"正在运行配置：{config_name}")
		self.正在处理的配置 = config
		self.重置运行日志()
		recall: Notice = {
			"payload": f"{format_time()}\n开始运行配置：{config_name}",
			"status": 'OK',
			"type": 'config_start',
			'config': self.生成回调消息中的配置信息(config, None)
			}
		self.待发送的消息队列.put(recall)

		task_index = 0
		retry = 0
		已经成功执行的核心任务name: list[str] = []
		self.已实际执行过的Fight任务name: list[str] = []
		self.已启用的任务name: list[str]  = []
		self.作战任务阻塞标记 = False

		for task in config["tasks"]:
			if "enable" in task:
				if task["enable"]:
					self.已启用的任务name.append(task["name"])
			else:
				self.已启用的任务name.append(task["name"])

		self.重置运行日志()

		任务总数 = len(config["tasks"])
		while task_index < 任务总数:
			self.检查退出信号()
			self.任务执行结果 = ['正常']
			begin_time = time.perf_counter()
			lg.info(f"正在处理第{task_index}个任务")
			task = config["tasks"][task_index]
			self.正在处理的任务 = task
			lg.info(task)
			recall: Notice = {
				'config': self.生成回调消息中的配置信息(config, task),
				'duration':0,
				'status':'SUCCESS',
				'payload':'',
				'type':'task_result'
			}
			self.重置运行日志()
			task_index += 1
			if task["type"] == "Update":
				lg.info("收到更新任务，调用更新和加载函数")
				self.更新并加载MAA核心和共享库(force=True)
				continue

			lg.info(f"当前已执行了的核心任务:{已经成功执行的核心任务name=}")
			if task["name"] in 已经成功执行的核心任务name:
				lg.info("跳过已执行了的核心任务")
				continue

			lg.info("检查任务是否启用")
			if "enable" in task and task["enable"] is False:
				lg.info("该任务未启用，跳过")
				continue

			lg.info("检查任务是否被阻塞")
			if self.作战任务阻塞标记 and task["type"] == "Fight":
				lg.info("该任务被阻塞，跳过")
				continue

			if "block" in task and task["block"] == "enable":
				self.作战任务阻塞标记 = True
				lg.info("检查到配置项[启动时阻塞]已启用，已设置阻塞标记，阻止之后的所有战斗任务执行")

			if "condition" in task:
				if not self.任务运行条件检查(task["condition"]):
					lg.info("任务条件检查未通过，跳过当前任务")
					continue

			lg.info("检查完毕：任务正常启用")

			lg.info("运行任务前检查ADB连接情况")
			if not self.connect():
				lg.error("连接失败，放弃该配置的运行")
				recall["status"] = "FAILED"
				recall["payload"] = self.运行日志["connect"]
				recall["duration"] = int(time.perf_counter() - begin_time)
				self.待发送的消息队列.put(recall)
				break
			lg.info("检查完毕：ADB连接正常")

			lg.info("准备提交任务")
			if "params" in task:
				self.maa.append_task(task["type"], task["params"])
			else:
				self.maa.append_task(task["type"])

			lg.info("检查是否需要在运行前截图")
			img_msg: bytes | None = None
			screenshot_path: str = ''
			if "screenshot" in task and task["screenshot"] in ("before","both"):
				img_name = f"before_{task['name']}"
				screenshot_path = str(Path(__file__).parent.parent / f"data/img/{img_name}.png")
				img_msg = self.立即截图(img_name)
				lg.info(f"截图完成，图片大小 {len(img_msg)/1024}KB")

			lg.info("启动MAA运行")
			self.maa.start()
			lg.info("循环等待MAA执行任务结束")
			while self.maa.running():
				self.检查退出信号()
				self.检查重要通知并发送(recall)
				time.sleep(1)
			lg.success("任务结束运行")
			lg.info(f"检查结束标记：{self.任务执行结果}")


			if "MAA出错" in self.任务执行结果:
				text = "任务运行过程中存在出错情况，具体问题定位有待代码完善"
				recall["payload"] += text + "\n"

			if "剿灭" in task["name"]:
				self.运行日志["fight"]["other_msg"] += "目前MAA的自动刷剿灭功能与结果统计不完善\n"

			for key in ('stages_drops_msg', 'other_msg', 'sanity'):
				if self.运行日志["fight"][key]:
					recall["payload"] += self.运行日志["fight"][key]+'\n'

			if len(self.运行日志["fight"]["stages"]) > 0:
				self.已实际执行过的Fight任务name.append(task["name"])
				if "block" in task and task["block"] == "executed":
					lg.info("检查到配置项[执行后阻塞]已启用，已设置阻塞标记，阻止之后的所有战斗任务执行")
					self.作战任务阻塞标记 = True

			lg.info(f"现在成功有效执行了的任务有：{self.已实际执行过的Fight任务name=}")

			for key in ('recruit', 'infrast', 'OperBox'):
				if self.运行日志[key]:
					recall["payload"] += self.运行日志[key]+"\n"

			if "关卡导航异常" in self.任务执行结果:
				text = "关卡导航异常，将无视block配置，继续执行后续备选作战任务"
				lg.error(text)
				recall["payload"] += text + '\n'
				recall["status"] = "FAILED"
				self.作战任务阻塞标记 = False

			elif "作战启动检查异常" in self.任务执行结果:
				lg.error(self.任务执行结果)
				if 'params' in task and "stage" in task["params"] and task["params"]["stage"][:2] in ["CE", "AP", "SK", "CA", "PR"]:
					self.作战任务阻塞标记 = False
					recall["payload"] += '可能是素材副本今日未开放，继续执行后续任务\n'
				else:
					lg.error("作战启动检查异常，先sleep五分钟等待作战结束再从头运行配置")
					recall["payload"] += '作战启动检查异常，先sleep五分钟等待可能正在进行的作战结束，而后从头重新运行配置\n'
					self.作战任务阻塞标记 = False
					task_index = 0
					self.maa.stop()
					time.sleep(5 * 60)
					continue
			elif "需要重连" in self.任务执行结果:
				text = "任务运行过程出错，重新尝试使用adb连接到安卓设备"
				lg.error(text)
				recall["payload"] += text + "\n"
				if not self.connect(init=True):
					text = "连接失败，放弃该配置的运行"
					lg.error(text)
					recall["status"] = "FAILED"
					recall["payload"] += self.运行日志["connect"] + "\n" + text+ "\n" 
					recall["duration"] = int(time.perf_counter() - begin_time)
					self.待发送的消息队列.put(recall)
					break
				self.任务执行结果 = ["正常"]
				self.作战任务阻塞标记 = False
				task_index = 0
				text = "MAA重连成功，尝试重新执行未完成的任务"
				lg.error(text)
				recall["payload"] += text+'\n'
				recall["status"] = "FAILED"
				recall["duration"] = int(time.perf_counter() - begin_time)
				self.待发送的消息队列.put(recall)
				self.maa.stop()
				continue
			elif "任务链出错" in self.任务执行结果:
				if retry < 2:
					retry += 1
					self.任务执行结果 = ["正常"]
					text = "任务运行过程出错，尝试重新从头执行该配置一次"
					self.作战任务阻塞标记 = False
					lg.error(text)
					recall["payload"] += text+"\n"
					recall["status"] = "FAILED"
					recall["duration"] = int(time.perf_counter() - begin_time)
					self.待发送的消息队列.put(recall)
					task_index = 0
					self.maa.stop()
					continue
				else:
					self.任务执行结果 = ["正常"]
					text = "任务运行过程出错且重试失败，放弃该配置"
					lg.error(text)
					recall["payload"] += text+"\n"
					recall["status"] = "FAILED"
					recall["duration"] = int(time.perf_counter() - begin_time)
					self.待发送的消息队列.put(recall)
					self.maa.stop()
					break

			lg.info("检查是否需要在运行后截图")
			if "screenshot" in task and task["screenshot"] in ("after","both"):
				img_name = f"after_{task['name']}"
				screenshot_path = str(Path(__file__).parent.parent / f"data/img/{img_name}.png")
				img_msg = self.立即截图(img_name)


			if (task["name"] == "任务完成后主界面"
				and img_msg
				and (datetime.datetime.now().hour >= 12 or datetime.datetime.now().hour < 4)):

				score=check_oops.检查免费单抽(screenshot_path)
				lg.info(f"检查免费单抽 {score=}")
				if score > 0.9:
					text = "!重要!  今天的免费单抽机会似乎还没用掉，请在任务结束后检查\n"
					lg.info(text)
					recall["payload"] += text
				else:
					lg.info("未检查到有没用掉的免费单抽")

				score=check_oops.检查活动红点(screenshot_path)
				lg.info(f"检查活动红点 {score=}")
				if score > 0.9:
					text = "!重要!  今天的活动奖励还未领取（紧张刺激的签到活动或合成玉抽签），请在任务结束后检查\n"
					lg.info(text)
					recall["payload"] += text
				else:
					lg.info("未检查到有活动红点")

				score=check_oops.检查基建异常(screenshot_path)
				lg.info(f"检查基建异常 {score=}")
				if score > 0.9:
					text = "!重要!  基建的某些设施似乎存在异常，请在任务结束后检查\n"
					lg.info(text)
					recall["payload"] += text
				else:
					lg.info("未检查到基建设施异常")

			if (task["type"] != "Custom"
				and task["type"] != "CloseDown"
				and task["type"] != "StartUp"):
				已经成功执行的核心任务name.append(task["name"])
				lg.info(f"更新最近一个已完成的核心任务为：{task["name"]}，目前{已经成功执行的核心任务name=}")

			if img_msg:
				lg.info("将截图填入回调消息中")
				recall["image"] = base64.b64encode(img_msg).decode("utf-8")

			if "跳过当前配置" in self.任务执行结果:
				text = "收到指令，终止当前配置运行"
				lg.error(text)
				recall["payload"] += text+"\n"
				recall["duration"] = int(time.perf_counter() - begin_time)
				self.待发送的消息队列.put(recall)
				self.maa.stop()
				return

			if "停止所有配置" in self.任务执行结果:
				text = "收到指令，终止所有配置运行"
				lg.error(text)
				recall["payload"] += text + '\n'
				recall["duration"] = int(time.perf_counter() - begin_time)
				self.待发送的消息队列.put(recall)
				self.maa.stop()
				return

			lg.info("正常发送回调消息")
			recall["duration"] = int(time.perf_counter() - begin_time)
			self.待发送的消息队列.put(recall)

			lg.info("清理任务队列，等待后续任务执行")
			self.任务执行结果 = ["正常"]
			# retry = 0
			self.maa.stop()

		recall = {
			"payload": f"{format_time()}\n一般配置运行结束：{config['id']}",
			"status": "OK",
			"type": "config_end",
			'config': self.生成回调消息中的配置信息(config, None)
			}
		self.待发送的消息队列.put(recall)
		self.导出cache()

	def 生成回调消息中的配置信息(self, config:TaskConfig, task: Task | None):
		ret: TaskConfig = {
			'id': config["id"],
			'type': config["type"],
			'tasks': [task.copy()] if task is not None else []
				}
		for key, value in config.items():
			if key not in ('id','type','tasks'):
				ret[key] = value
		return ret

	def 检查重要通知并发送(self, recall: Notice):
		if self.运行日志['important'] != '':
			tmp = recall.copy()
			tmp["payload"] = f"{format_time()}\n{self.正在处理的配置['id']}\n{self.运行日志['important']}"
			tmp["type"] ='important_notice'
			tmp["status"] = 'OK'
			self.待发送的消息队列.put(tmp)
			self.运行日志['important'] = ''
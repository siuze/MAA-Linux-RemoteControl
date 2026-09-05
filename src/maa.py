import base64
from collections import deque
import datetime
import json5 as json
import os
import time
from typing import Any, Literal, TypedDict
from pathlib import Path

import yaml
from .asst.asst import Asst
from .asst.updater import Updater
from .asst.utils import InstanceOptionType, Message, Version
from loguru import logger as lg
from multiprocessing.queues import Queue as QUEUE
from src._global import ErrorCode, Notice, TaskCondition, TaskConfig, Task, facility_translate
from src import check_oops, cache
from src.process_utils import run_cmd, CommandTimeoutError


class MaaRestartRequest(Exception):
	"""请求优雅重启 MAA 子进程异常"""
	pass


class FightLog(TypedDict):
	stages: dict[str, int]
	drops: dict[str, int]
	stages_drops_msg: str
	other_msg: str
	sanity: str


class RuningLog(TypedDict):
	connect: str
	fight: FightLog
	recruit: str
	infrast: str
	OperBox: str
	important: str


_CURRENT_MAA: Any = None


@Asst.CallBackType
def my_callback(msg: int, details: bytes, arg: Any) -> None:
	"""
	MAA-CORE的运行消息回调函数
	:params:
			``msg``: 消息类型
			``details``:  消息具体内容
	:return: None
	"""
	global _CURRENT_MAA
	self: MAA | None = _CURRENT_MAA
	if self is None or not self.inited:
		return

	try:
		消息类型 = Message(msg)
		json消息内容 = json.loads(details.decode("utf-8"))
	except Exception as e:
		lg.warning(f"解析 MAA 回调消息失败: {e!r}")
		return

	if 消息类型 in (Message.InternalError, Message.SubTaskError, Message.TaskChainError):
		lg.error(f"MAA出错：{str(消息类型)} {json消息内容}")
	if 消息类型 == Message.TaskChainError and json消息内容.get("taskchain") not in ("Custom", "Roguelike"):
		self.任务执行结果.append("任务链出错")
		try:
			self.maa.stop()
		except Exception:
			pass
	elif 消息类型 == Message.SubTaskError:
		if "first" in json消息内容 and json消息内容["first"] and json消息内容["first"][0] == "FightBegin":
			self.任务执行结果.append("作战启动检查异常")
			try:
				self.maa.stop()
			except Exception:
				pass
		if "subtask" in json消息内容 and json消息内容["subtask"] == "StageNavigationTask":
			self.任务执行结果.append("关卡导航异常")
			try:
				self.maa.stop()
			except Exception:
				pass
	elif 消息类型 == Message.AsyncCallInfo:
		text = f"收到异步调用的回调消息：{str(消息类型)} {details.decode('utf-8', errors='replace')}"
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
			try:
				self.maa.stop()
			except Exception:
				pass
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
			self.运行日志["infrast"] += f"{facility_translate.get(json消息内容['details']['facility'], json消息内容['details']['facility'])}可用干员不足\n"
		elif what == "InfrastTrainingCompleted":
			self.运行日志["infrast"] += f"!重要! 干员【{json消息内容['details']['operator']}】的技能【{json消息内容['details']['skill']}】专精【{json消息内容['details']['level']}】训练完成\n"
		elif what == "UseMedicine":
			text = f"使用{'即将过期' if json消息内容['details']['is_expiring'] else ''}理智药{json消息内容['details']['count']}个\n"
			self.运行日志["fight"]["other_msg"] += text
			self.运行日志["important"] += text
		elif what == "SanityBeforeStage":
			self.运行日志["fight"]["sanity"] = f"剩余理智 {json消息内容['details']['current_sanity']}/{json消息内容['details']['max_sanity']}"
		elif what == "OperBoxInfo":
			if json消息内容["details"]["done"]:
				text = "尚未获得的干员："
				own: list[str] = []
				not_own: list[str] = []
				for it in json消息内容["details"]["all_opers"]:
					if it["own"] is False:
						if it["name"].startswith("预备干员"):
							continue
						if it["name"] in ("Misery", "郁金香", "Pith", "Sharp", "阿米娅-WARRIOR", "阿米娅-MEDIC", "Touch", "Raidian", "Mechanist", "Stormeye"):
							continue
						text += f"{it['name']}，"
						not_own.append(it["name"])
					else:
						own.append(it["name"])
				if text[-1:] == "，":
					text = text[:-1]
				text += "\n（MAA干员识别功能尚不完善，可能出现错识别、漏识别的问题）"
				lg.info(own)
				lg.info(not_own)
				lg.info(text)
				self.运行日志["OperBox"] = text
		elif what == "NotThreeStars":
			stage = ""
			if "params" in self.正在处理的任务 and "stage" in self.正在处理的任务["params"]:
				stage = self.正在处理的任务["params"]["stage"]
			text = f"未能三星通关作战关卡{stage}，请在任务结束后检查代理是否稳定\n"
			self.运行日志["fight"]["other_msg"] += text
			self.运行日志["important"] += text

	if "details" in json消息内容:
		if "task" in json消息内容["details"]:
			if json消息内容["details"]["task"] == "StoneConfirm" and 消息类型 == Message.SubTaskCompleted:
				self.运行日志["fight"]["other_msg"] += "确认碎石一次\n"
			if json消息内容["details"]["task"] == "InfrastDormDoubleConfirmButton":
				self.运行日志["infrast"] += "基建宿舍出现干员冲突，请检查\n"

	if hasattr(self, "运行配置") and self.运行配置.get("python", {}).get("debug", False):
		lg.debug(消息类型)
		lg.debug(json消息内容)


def format_time() -> str:
	return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class MAA:
	__slots__ = (
		"待执行的一般配置队列",
		"待执行的中断配置队列",
		"待发送的消息队列",
		"正在处理的配置",
		"正在处理的任务",
		"已实际执行过的Fight任务name",
		"已启用的任务name",
		"作战任务阻塞标记",
		"任务执行结果",
		"MAA内核路径",
		"运行配置",
		"退出信号",
		"运行日志",
		"maa",
		"inited",
		"作战启动检查异常计数",
	)

	def __init__(self) -> None:
		global _CURRENT_MAA
		self.inited = False
		self.作战启动检查异常计数 = 0
		self.maa = None
		self.退出信号 = False
		self.作战任务阻塞标记 = False
		self.已实际执行过的Fight任务name = []
		self.已启用的任务name = []
		self.任务执行结果 = ["正常"]
		self.正在处理的配置 = {"id": "", "type": "normal", "tasks": [], "priority": 0}
		self.正在处理的任务 = {"type": "StartUp", "name": ""}
		_CURRENT_MAA = self

	def init(
		self,
		待执行的一般配置队列: deque[TaskConfig],
		待执行的中断配置队列: deque[TaskConfig],
		待发送的消息队列: QUEUE[Notice],
	) -> None:
		self.待执行的一般配置队列 = 待执行的一般配置队列
		self.待执行的中断配置队列 = 待执行的中断配置队列
		self.待发送的消息队列 = 待发送的消息队列
		self.运行日志: RuningLog = {
			"connect": "",
			"fight": {
				"stages": {},
				"drops": {},
				"other_msg": "",
				"stages_drops_msg": "",
				"sanity": "",
			},
			"recruit": "",
			"infrast": "",
			"OperBox": "",
			"important": "",
		}
		self.MAA内核路径 = Path(__file__).parent.parent.parent / "MAA-linux"
		with open(Path(__file__).parent.parent / "config.yaml", "r", encoding="utf8") as config_f:
			self.运行配置 = yaml.safe_load(config_f)

		self.更新并加载MAA核心和共享库()
		self.inited = True

	def destroy(self) -> None:
		"""
		优雅析构 MAA 实例与底层关联资源。
		彻底终止底层的 MaaTouch / ADB 进程，防止产生孤儿进程。
		"""
		global _CURRENT_MAA
		lg.info("正在执行 MAA 实例析构与资源释放...")
		try:
			if hasattr(self, "maa") and self.maa is not None:
				try:
					if self.maa.running():
						self.maa.stop()
				except Exception:
					pass
				del self.maa
				self.maa = None
		except Exception as e:
			lg.warning(f"释放 MAA 实例时出错: {e!r}")
		_CURRENT_MAA = None
		self.inited = False

	def 重置运行日志(self) -> None:
		self.运行日志["connect"] = ""
		self.运行日志["fight"]["stages"] = {}
		self.运行日志["fight"]["drops"] = {}
		self.运行日志["fight"]["other_msg"] = ""
		self.运行日志["fight"]["sanity"] = ""
		self.运行日志["fight"]["stages_drops_msg"] = ""
		self.运行日志["important"] = ""
		self.运行日志["infrast"] = ""
		self.运行日志["recruit"] = ""
		self.运行日志["OperBox"] = ""

	def 启动子进程(self, cmd: str, timeout: float = 30.0, skip: bool = False) -> bytes:
		"""
		安全执行 Linux 命令。
		通过 run_cmd 进行全生命周期受控执行，杜绝管道缓冲区死锁与 SIGUSR1 残留僵尸。
		"""
		try:
			return run_cmd(cmd, timeout=timeout, skip_timeout=skip)
		except CommandTimeoutError:
			lg.error(f"命令执行超时: {cmd}")
			raise
		except Exception as e:
			lg.error(f"执行命令发生异常: {cmd}, {e!r}")
			raise

	def 导出cache(self) -> None:
		cache.导出_cache(self.待执行的一般配置队列, self.待执行的中断配置队列)

	def 检查退出信号(self) -> None:
		if self.退出信号:
			lg.info("检查到退出标记，执行优雅退出")
			self.destroy()
			raise MaaRestartRequest("接收到退出信号，退出当前子进程")

	def 更新并加载MAA核心和共享库(self, force: bool = False) -> None:
		self.检查退出信号()
		lg.info("进入版本更新与加载函数")
		proxies = None
		if "proxy" in self.运行配置.get("python", {}) and self.运行配置["python"]["proxy"]:
			proxies = {"http": self.运行配置["python"]["proxy"], "https": self.运行配置["python"]["proxy"]}

		if self.运行配置.get("python", {}).get("auto_update", False) or force:
			lg.info(f"开始更新 {self.MAA内核路径=}")
			try:
				已实际更新, 已实际OTA, 更新日志 = Updater(
					maa_内核路径=self.MAA内核路径, maa版本类型=Version.Beta, http代理=proxies
				).update()
				status = "OK"
				if 已实际更新 or 已实际OTA:
					status = "SUCCESS"
				recall: Notice = {
					"status": status,
					"payload": 更新日志.rstrip(),
					"type": "update_log",
					"code": ErrorCode.SUCCESS,
				}
				self.待发送的消息队列.put(recall)
				lg.info("更新流程结束")
				if status == "SUCCESS":
					lg.info("核心文件已有更新，保存缓存并请求优雅重启以加载新共享库")
					self.导出cache()
					self.destroy()
					raise MaaRestartRequest("核心文件版本发生变化，优雅退出等待重启")
			except MaaRestartRequest:
				raise
			except Exception as e:
				lg.exception(f"版本更新时发生异常: {e!r}")
				recall: Notice = {
					"status": "FAILED",
					"payload": f"进行版本更新时发生异常 {e!r}",
					"type": "update_log",
					"code": ErrorCode.ERR_MAA_CRASH,
				}
				self.待发送的消息队列.put(recall)
		else:
			lg.info("未开启自动更新")

		self.添加自定义任务()
		lg.info("添加自定义任务模块结束")

		Asst.load(path=self.MAA内核路径, incremental_path=self.MAA内核路径 / "cache")
		lg.info("加载资源结束")

		self.maa = Asst(callback=my_callback)
		lg.info("构造Asst并设置回调函数结束")

		self.maa.set_instance_option(
			InstanceOptionType.touch_type, self.运行配置.get("instance_options", {}).get("touch_mode", "maatouch")
		)
		lg.info("加载完成")

	def 添加自定义任务(self) -> None:
		self.检查退出信号()
		custom_tasks_path = Path(__file__).parent.parent / "data/patch/tasks.json"
		official_tasks_path = self.MAA内核路径 / "resource/tasks/tasks.json"
		if os.path.exists(custom_tasks_path) and os.path.exists(official_tasks_path):
			try:
				with open(custom_tasks_path, "r", encoding="utf8") as file:
					customs_tasks = json.load(file)
				with open(official_tasks_path, "r", encoding="utf8") as file:
					official_tasks = json.load(file)
				for key, values in customs_tasks.items():
					official_tasks[key] = values
				with open(official_tasks_path, "w", encoding="utf8") as file:
					file.write(json.dumps(official_tasks, ensure_ascii=False, indent=4, quote_keys=True, separators=(", ", ": ")))
			except Exception as e:
				lg.error(f"合并自定义任务失败: {e!r}")

		custom_template_path = Path(__file__).parent.parent / "data/patch/template"
		official_template_path = self.MAA内核路径 / "resource/template/WakeUp/AccountManager"
		if os.path.exists(custom_template_path) and os.path.exists(official_template_path):
			try:
				for template in os.listdir(custom_template_path):
					custom_template_file_path = os.path.join(custom_template_path, template)
					official_template_file_path = os.path.join(official_template_path, template)
					with open(custom_template_file_path, "rb") as custom_f:
						with open(official_template_file_path, "wb") as official_f:
							official_f.write(custom_f.read())
			except Exception as e:
				lg.error(f"复制自定义模板失败: {e!r}")

		custom_ota_tasks_path = Path(__file__).parent.parent / "data/patch/cache/resource/tasks.json"
		official_ota_tasks_path = self.MAA内核路径 / "cache/resource/tasks.json"
		if os.path.exists(custom_ota_tasks_path) and os.path.exists(official_ota_tasks_path):
			try:
				with open(custom_ota_tasks_path, "r", encoding="utf8") as file:
					customs_tasks = json.load(file)
				with open(official_ota_tasks_path, "r", encoding="utf8") as file:
					official_tasks = json.load(file)
				for key, values in customs_tasks.items():
					official_tasks[key] = values
				with open(official_ota_tasks_path, "w", encoding="utf8") as file:
					file.write(json.dumps(official_tasks, ensure_ascii=False, indent=4, quote_keys=True, separators=(", ", ": ")))
			except Exception as e:
				lg.error(f"合并 OTA 自定义任务失败: {e!r}")

	def clean_adb(self) -> None:
		"""安全重启 ADB 服务，避免误杀系统级 adbd"""
		try:
			self.检查退出信号()
			adb_bin = self.运行配置["connection"]["adb"]
			self.启动子进程(f"{adb_bin} kill-server", timeout=10.0)
		except Exception as e:
			lg.warning(f"clean_adb 执行异常: {e!r}")

	def find_adb_wifi_port(self, retry: int = 50) -> int:
		"""Android 11+ 无线调试端口动态扫描"""
		try:
			ip = self.运行配置["connection"]["ip"]
			while retry:
				self.检查退出信号()
				cmd = f'nmap {ip} -p 30000-49999 | awk "/\\/tcp/" | cut -d/ -f1'
				try:
					out = self.启动子进程(cmd=cmd, timeout=30.0)
					port = out.decode("utf8", errors="replace").replace(" ", "").replace("\n", "")
					lg.info(f"扫描得到 ADB 端口为：{port}")
					if port and port.isdigit():
						self.运行配置["connection"]["port"] = int(port)
						return int(port)
				except Exception as e:
					lg.warning(f"扫描端口子进程出错: {e!r}")

				lg.error("未扫描到设备 ADB 端口，等待 5s 重试")
				time.sleep(5)
				retry -= 1

			lg.error("扫描不到设备 ADB 端口，放弃重试")
			return 0
		except Exception as e:
			lg.exception(f"find_adb_wifi_port 异常: {e!r}")
			return 0

	def connect_adb(self) -> bool:
		"""通过 ADB 直接连接到安卓设备"""
		try:
			self.检查退出信号()
			if self.运行配置["connection"].get("scan_port", False) and not self.find_adb_wifi_port():
				return False
			ip = self.运行配置["connection"]["ip"]
			port = self.运行配置["connection"]["port"]
			adb_bin = self.运行配置["connection"]["adb"]
			cmd = f"{adb_bin} connect {ip}:{port}"
			out = self.启动子进程(cmd=cmd, timeout=15.0)
			result = out.decode("utf8", errors="replace").replace(" ", "").replace("\n", "")
			lg.info(f"ADB 连接结果：{result}")
			return "already" in result or "connected" in result
		except Exception as e:
			lg.exception(f"connect_adb 异常: {e!r}")
			return False

	def connect(self, init: bool = False, retry: int = 0) -> bool:
		self.检查退出信号()
		if self.maa is not None and self.maa.connected():
			text = "MAA当前已经通过ADB连接到安卓设备了，不需要重新连接"
			lg.info(text)
			self.运行日志["connect"] = text
			return True

		text = f"第{retry}次尝试连接ADB"
		self.运行日志["connect"] = text
		lg.info(text)

		if (init or retry) and self.运行配置["connection"].get("scan_port", False):
			if not self.find_adb_wifi_port():
				return False

		ip = self.运行配置["connection"]["ip"]
		port = self.运行配置["connection"]["port"]
		text = f"尝试连接到：{ip}:{port}"
		lg.info(text)
		self.运行日志["connect"] += "\n" + text

		self.connect_adb()
		if self.maa.connect(
			adb_path=self.运行配置["connection"]["adb"],
			address=f"{ip}:{port}",
			config=self.运行配置["connection"].get("config", "CompatPOSIXShell"),
		):
			text = "连接成功"
			lg.info(text)
			self.运行日志["connect"] += "\n" + text
			try:
				self.立即截图("连接成功后")
			except Exception:
				pass
			return True
		else:
			if retry < 5:
				lg.error("连接失败，准备重连")
				time.sleep(2)
				return self.connect(retry=retry + 1)
			else:
				text = f"连接失败，请检查 MAA-CORE 日志，位于 {self.MAA内核路径}/debug/asst.log"
				lg.error(text)
				self.运行日志["connect"] += text + "\n"
				return False

	def 立即截图(self, file_name: str) -> bytes:
		try:
			self.检查退出信号()
			img_dir = Path(__file__).parent.parent / "data/img"
			img_dir.mkdir(parents=True, exist_ok=True)
			img_path = str(img_dir / f"{file_name}.png")
			ip = self.运行配置["connection"]["ip"]
			port = self.运行配置["connection"]["port"]
			adb_bin = self.运行配置["connection"]["adb"]
			shell_cmd = f"{adb_bin} -s {ip}:{port} exec-out screencap -p > {img_path}"
			self.启动子进程(shell_cmd, timeout=20.0)
			with open(img_path, "rb") as f:
				img = f.read()
			lg.info(f"截图完成: {file_name}, 大小: {len(img)/1024:.2f} KB")
			return img
		except Exception as e:
			lg.warning(f"立即截图失败 [{file_name}]: {e!r}")
			return b""

	def 更新作战结果日志(self, detail: dict[str, Any]) -> None:
		self.检查退出信号()
		stage = detail["stage"]["stageCode"]
		cur_times = detail.get("cur_times", 1)
		if stage not in self.运行日志["fight"]["stages"]:
			self.运行日志["fight"]["stages"][stage] = cur_times
		else:
			self.运行日志["fight"]["stages"][stage] += cur_times

		for drop in detail.get("stats", []):
			self.运行日志["fight"]["drops"][drop["itemName"]] = drop["quantity"]

		self.运行日志["fight"]["stages_drops_msg"] = "作战结果：\n"
		for key, value in self.运行日志["fight"]["stages"].items():
			self.运行日志["fight"]["stages_drops_msg"] += f"  {key} * {value}\n"
		self.运行日志["fight"]["stages_drops_msg"] += "战斗掉落：\n"
		for key, value in self.运行日志["fight"]["drops"].items():
			self.运行日志["fight"]["stages_drops_msg"] += f"  {key} * {value}\n"
		self.运行日志["fight"]["stages_drops_msg"] = self.运行日志["fight"]["stages_drops_msg"].rstrip()

	def 任务运行逻辑条件检查(self, operator: Literal["executed", "enable", "not", "and", "or"], cond: Any) -> bool:
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
		return True

	def 任务运行条件检查(self, cond: TaskCondition) -> bool:
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
		for key in ("not", "and", "or"):
			if key in cond:
				lg.info("检查逻辑条件")
				if not self.任务运行逻辑条件检查(key, cond[key]):  # type: ignore
					return False
		return enable

	def 执行中断任务配置(self, config: TaskConfig) -> None:
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
			"type": "config_start",
			"config": self.生成回调消息中的配置信息(config, None),
			"code": ErrorCode.SUCCESS,
		}
		self.待发送的消息队列.put(recall)

		task_index = 0
		while task_index < len(config["tasks"]):
			self.检查退出信号()
			lg.success(f"正在处理第{task_index}个中断任务")
			task = config["tasks"][task_index]
			lg.success(task)
			task_index += 1
			recall = {
				"type": "task_result",
				"status": "SUCCESS",
				"payload": "",
				"config": self.生成回调消息中的配置信息(config, task),
				"image": "",
				"duration": 0,
				"code": ErrorCode.SUCCESS,
			}
			time_begin = time.perf_counter()
			if task["type"] == "Screenshot":
				img_msg = self.立即截图(f"Interrupt_{task['name']}")
				if len(img_msg) < 10 * 1024:
					text = f"截图数据大小异常（{round(len(img_msg)/1024, 2)}KBytes），尝试重连ADB"
					lg.error(text)
					if not self.connect_adb():
						text = "\n重连失败，请排查错误"
						lg.error(text)
						recall["payload"] = text
						recall["status"] = "FAILED"
						recall["code"] = ErrorCode.ERR_ADB_SCREENCAP_FAILED
					else:
						img_msg = self.立即截图(f"Interrupt_{task['name']}")
						if len(img_msg) < 10 * 1024:
							text = f"\n截图数据异常（{round(len(img_msg)/1024, 2)}KBytes）且重连无效，请排查错误"
							lg.error(text)
							recall["payload"] = text
						else:
							recall["image"] = base64.b64encode(img_msg).decode("utf-8")
				else:
					recall["image"] = base64.b64encode(img_msg).decode("utf-8")

			elif task["type"] == "Stop_config":
				if "params" in task:
					需要删除的配置名 = task["params"]["id"]
					if self.正在处理的配置.get("id") != 需要删除的配置名:
						lg.info("准备清除一份尚未运行的配置")
						cleaned = False
						for _ in range(len(self.待执行的一般配置队列)):
							del_config = self.待执行的一般配置队列.popleft()
							if del_config.get("id") != 需要删除的配置名:
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
						if self.maa:
							self.maa.stop()
						recall["payload"] += f"已下发指令：终止当前正在运行的配置【{需要删除的配置名}】"

			elif task["type"] == "Stop":
				lg.info("停止maa当前任务并设置标记：停止所有配置")
				self.任务执行结果.append("停止所有配置")
				self.待执行的一般配置队列.clear()
				if self.maa:
					self.maa.stop()
				recall["payload"] = "已下发指令：停止所有配置的运行"

			lg.info("发送回调消息")
			recall["duration"] = int(time.perf_counter() - time_begin)
			self.待发送的消息队列.put(recall)

		end_notice: Notice = {
			"payload": f"{format_time()}\n中断配置运行结束：{config['id']}",
			"status": "OK",
			"type": "config_end",
			"config": self.生成回调消息中的配置信息(config, None),
			"code": ErrorCode.SUCCESS,
		}
		self.待发送的消息队列.put(end_notice)
		self.导出cache()

	def 执行一般任务配置(self, config: TaskConfig) -> None:
		self.检查退出信号()
		config_name = config["id"]
		lg.info(f"正在运行配置：{config_name}")
		self.正在处理的配置 = config
		self.重置运行日志()
		recall: Notice = {
			"payload": f"{format_time()}\n开始运行配置：{config_name}",
			"status": "OK",
			"type": "config_start",
			"config": self.生成回调消息中的配置信息(config, None),
			"code": ErrorCode.SUCCESS,
		}
		self.待发送的消息队列.put(recall)

		task_index = 0
		retry = 0
		已经成功执行的核心任务name: list[str] = []
		self.已实际执行过的Fight任务name = []
		self.已启用的任务name = []
		self.作战任务阻塞标记 = False

		for task in config.get("tasks", []):
			if task.get("enable", True):
				self.已启用的任务name.append(task["name"])

		self.重置运行日志()

		任务总数 = len(config.get("tasks", []))
		while task_index < 任务总数:
			self.检查退出信号()
			self.任务执行结果 = ["正常"]
			begin_time = time.perf_counter()
			lg.success(f"正在处理第{task_index}个任务")
			task = config["tasks"][task_index]
			self.正在处理的任务 = task
			lg.success(task)

			task_recall: Notice = {
				"config": self.生成回调消息中的配置信息(config, task),
				"duration": 0,
				"status": "SUCCESS",
				"payload": "",
				"type": "task_result",
				"code": ErrorCode.SUCCESS,
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
			if not task.get("enable", True):
				lg.info("该任务未启用，跳过")
				continue

			lg.info("检查任务是否被阻塞")
			if self.作战任务阻塞标记 and task["type"] == "Fight":
				lg.info("该任务被阻塞，跳过")
				continue

			if task.get("block") == "enable":
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
				task_recall["status"] = "FAILED"
				task_recall["code"] = ErrorCode.ERR_ADB_CONNECT_FAILED
				task_recall["payload"] = self.运行日志["connect"]
				task_recall["duration"] = int(time.perf_counter() - begin_time)
				self.待发送的消息队列.put(task_recall)
				break
			lg.info("检查完毕：ADB连接正常")

			lg.info("准备提交任务")
			if "params" in task:
				self.maa.append_task(task["type"], task["params"])
			else:
				self.maa.append_task(task["type"])

			lg.info("检查是否需要在运行前截图")
			img_msg: bytes = b""
			screenshot_path = ""
			if task.get("screenshot") in ("before", "both"):
				img_name = f"before_{task['name']}"
				screenshot_path = str(Path(__file__).parent.parent / f"data/img/{img_name}.png")
				img_msg = self.立即截图(img_name)
				lg.info(f"截图完成，图片大小 {len(img_msg)/1024}KB")

			lg.info("启动MAA运行")
			self.maa.start()
			lg.info("循环等待MAA执行任务结束")
			while self.maa.running():
				self.检查退出信号()
				self.检查重要通知并发送(task_recall)
				self.检查高优先级任务()
				time.sleep(1)

			lg.success("任务结束运行")
			lg.info(f"检查结束标记：{self.任务执行结果}")

			if "MAA出错" in self.任务执行结果:
				text = "任务运行过程中存在出错情况，具体问题定位有待代码完善"
				task_recall["payload"] += text + "\n"

			if "剿灭" in task["name"]:
				self.运行日志["fight"]["other_msg"] += "目前MAA的自动刷剿灭功能与结果统计不完善\n"

			for key in ("stages_drops_msg", "other_msg", "sanity"):
				if self.运行日志["fight"][key]:
					task_recall["payload"] += self.运行日志["fight"][key] + "\n"

			if len(self.运行日志["fight"]["stages"]) > 0:
				self.已实际执行过的Fight任务name.append(task["name"])
				if task.get("block") == "executed":
					lg.info("检查到配置项[执行后阻塞]已启用，已设置阻塞标记，阻止之后的所有战斗任务执行")
					self.作战任务阻塞标记 = True

			lg.info(f"现在成功有效执行了的任务有：{self.已实际执行过的Fight任务name=}")

			for key in ("recruit", "infrast", "OperBox"):
				if self.运行日志[key]:
					task_recall["payload"] += self.运行日志[key] + "\n"

			if "关卡导航异常" in self.任务执行结果:
				text = "关卡导航异常，将无视block配置，继续执行后续备选作战任务"
				lg.error(text)
				task_recall["payload"] += text + "\n"
				task_recall["status"] = "FAILED"
				task_recall["code"] = ErrorCode.ERR_STAGE_NAVIGATION
				self.作战任务阻塞标记 = False

			elif "作战启动检查异常" in self.任务执行结果:
				lg.error(self.任务执行结果)
				if "params" in task and task["params"].get("stage", "")[:2] in ["CE", "AP", "SK", "CA", "PR"]:
					self.作战任务阻塞标记 = False
					task_recall["payload"] += "可能是素材副本今日未开放，继续执行后续任务\n"
					task_recall["code"] = ErrorCode.ERR_STAGE_NOT_OPEN
				elif "params" in task and task["params"].get("stage") == "Annihilation":
					self.作战任务阻塞标记 = False
					task_recall["payload"] += "作战启动检查异常，可能是剿灭已完成，继续执行后续任务\n"
				elif self.作战启动检查异常计数 > 0:
					lg.error("作战启动检查异常多次，放弃重试，继续执行后续任务")
					task_recall["payload"] += "作战启动检查异常多次，放弃重试，继续执行后续任务\n"
					task_recall["code"] = ErrorCode.ERR_FIGHT_START_FAILED
					self.作战任务阻塞标记 = False
				else:
					lg.error("作战启动检查异常，先sleep五分钟等待作战结束再从头运行配置")
					task_recall["payload"] += "作战启动检查异常，先sleep五分钟等待可能正在进行的作战结束，而后从头重新运行配置\n"
					self.作战任务阻塞标记 = False
					task_index = 0
					self.maa.stop()
					self.作战启动检查异常计数 += 1
					time.sleep(5 * 60)
					continue

			elif "需要重连" in self.任务执行结果:
				text = "任务运行过程出错，重新尝试使用adb连接到安卓设备"
				lg.error(text)
				task_recall["payload"] += text + "\n"
				if not self.connect(init=True):
					text = "连接失败，放弃该配置的运行"
					lg.error(text)
					task_recall["status"] = "FAILED"
					task_recall["code"] = ErrorCode.ERR_ADB_CONNECT_FAILED
					task_recall["payload"] += self.运行日志["connect"] + "\n" + text + "\n"
					task_recall["duration"] = int(time.perf_counter() - begin_time)
					self.待发送的消息队列.put(task_recall)
					break
				self.任务执行结果 = ["正常"]
				self.作战任务阻塞标记 = False
				task_index = 0
				text = "MAA重连成功，尝试重新执行未完成的任务"
				lg.error(text)
				task_recall["payload"] += text + "\n"
				task_recall["status"] = "FAILED"
				task_recall["duration"] = int(time.perf_counter() - begin_time)
				self.待发送的消息队列.put(task_recall)
				self.maa.stop()
				continue

			elif "任务链出错" in self.任务执行结果 and task["type"] not in ("Award",):
				if retry < 2:
					retry += 1
					self.任务执行结果 = ["正常"]
					text = "任务运行过程出错，尝试重新从头执行该配置一次"
					self.作战任务阻塞标记 = False
					lg.error(text)
					task_recall["payload"] += text + "\n"
					task_recall["status"] = "FAILED"
					task_recall["code"] = ErrorCode.ERR_TASK_CHAIN_ERROR
					task_recall["duration"] = int(time.perf_counter() - begin_time)
					self.待发送的消息队列.put(task_recall)
					task_index = 0
					self.maa.stop()
					continue
				else:
					self.任务执行结果 = ["正常"]
					text = "任务运行过程出错且重试失败，放弃该配置"
					lg.error(text)
					task_recall["payload"] += text + "\n"
					task_recall["status"] = "FAILED"
					task_recall["code"] = ErrorCode.ERR_TASK_CHAIN_ERROR
					task_recall["duration"] = int(time.perf_counter() - begin_time)
					self.待发送的消息队列.put(task_recall)
					self.maa.stop()
					break

			lg.info("检查是否需要在运行后截图")
			if task.get("screenshot") in ("after", "both"):
				img_name = f"after_{task['name']}"
				screenshot_path = str(Path(__file__).parent.parent / f"data/img/{img_name}.png")
				img_msg = self.立即截图(img_name)

			if task["name"] == "任务完成后主界面" and img_msg and (datetime.datetime.now().hour >= 12 or datetime.datetime.now().hour < 4):
				score = check_oops.检查免费单抽(screenshot_path)
				lg.info(f"检查免费单抽 {score=}")
				if score > 0.9:
					text = "!重要!  今天的免费单抽机会似乎还没用掉，请在任务结束后检查\n"
					lg.info(text)
					task_recall["payload"] += text
				else:
					lg.info("未检查到有没用掉的免费单抽")

				score = check_oops.检查活动红点(screenshot_path)
				lg.info(f"检查活动红点 {score=}")
				if score > 0.9:
					text = "!重要!  今天的活动奖励还未领取（紧张刺激的签到活动或合成玉抽签），请在任务结束后检查\n"
					lg.info(text)
					task_recall["payload"] += text
				else:
					lg.info("未检查到有活动红点")

				score = check_oops.检查基建异常(screenshot_path)
				lg.info(f"检查基建异常 {score=}")
				if score > 0.9:
					text = "!重要!  基建的某些设施似乎存在异常，请在任务结束后检查\n"
					lg.info(text)
					task_recall["payload"] += text
				else:
					lg.info("未检查到基建设施异常")

			if task["type"] not in ("Custom", "CloseDown", "StartUp"):
				已经成功执行的核心任务name.append(task["name"])
				lg.info(f"更新最近一个已完成的核心任务为：{task['name']}，目前{已经成功执行的核心任务name=}")

			if img_msg:
				lg.info("将截图填入回调消息中")
				task_recall["image"] = base64.b64encode(img_msg).decode("utf-8")

			if "跳过当前配置" in self.任务执行结果:
				text = "收到指令，终止当前配置运行"
				lg.error(text)
				task_recall["payload"] += text + "\n"
				task_recall["code"] = ErrorCode.ERR_CONFIG_SKIPPED
				task_recall["duration"] = int(time.perf_counter() - begin_time)
				self.待发送的消息队列.put(task_recall)
				self.maa.stop()
				return

			if "停止所有配置" in self.任务执行结果:
				text = "收到指令，终止所有配置运行"
				lg.error(text)
				task_recall["payload"] += text + "\n"
				task_recall["code"] = ErrorCode.ERR_TASK_ABORTED
				task_recall["duration"] = int(time.perf_counter() - begin_time)
				self.待发送的消息队列.put(task_recall)
				self.maa.stop()
				return

			lg.info("正常发送回调消息")
			task_recall["duration"] = int(time.perf_counter() - begin_time)
			self.待发送的消息队列.put(task_recall)

			lg.info("清理任务队列，等待后续任务执行")
			self.任务执行结果 = ["正常"]
			self.maa.stop()

		end_notice: Notice = {
			"payload": f"{format_time()}\n一般配置运行结束：{config['id']}",
			"status": "OK",
			"type": "config_end",
			"config": self.生成回调消息中的配置信息(config, None),
			"code": ErrorCode.SUCCESS,
		}
		self.待发送的消息队列.put(end_notice)
		self.导出cache()

	def 生成回调消息中的配置信息(self, config: TaskConfig, task: Task | None) -> TaskConfig:
		ret: TaskConfig = {
			"id": config.get("id", ""),
			"type": config.get("type", "normal"),
			"tasks": [task.copy()] if task is not None else [],
			"priority": config.get("priority", 0),
		}
		for key, value in config.items():
			if key not in ("id", "type", "tasks"):
				ret[key] = value
		return ret

	def 检查重要通知并发送(self, recall: Notice) -> None:
		if self.运行日志.get("important"):
			tmp = recall.copy()
			tmp["payload"] = f"{format_time()}\n{self.正在处理的配置.get('id', '')}\n{self.运行日志['important']}"
			tmp["type"] = "important_notice"
			tmp["status"] = "OK"
			tmp["code"] = ErrorCode.SUCCESS
			self.待发送的消息队列.put(tmp)
			self.运行日志["important"] = ""

	def 检查高优先级任务(self) -> None:
		if self.正在处理的配置.get("priority", 0) < 0 and len(self.待执行的一般配置队列) > 0:
			lg.info("检测到更高优先级任务，停止当前任务")
			if self.maa is not None:
				self.maa.stop()

import json
import multiprocessing
import os
import platform
import re
import shutil
import tarfile
import zipfile

import requests
from loguru import logger as lg
from requests.packages.urllib3.exceptions import InsecureRequestWarning  # 消除https未验证警告

from .asst import Asst
from .utils import Version


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class Updater:
	# API的地址
	Mirrors = ["https://ota.maa.plus"]
	Summary_json = "/MaaAssistantArknights/api/version/summary.json"
	ota_tasks_url = "https://ota.maa.plus/MaaAssistantArknights/api/resource/tasks.json"

	@staticmethod
	def download_file(url, path, proxies=None):
		with requests.get(url, stream=True, proxies=proxies, verify=False) as r:
			with open(path, "wb") as f:
				shutil.copyfileobj(r.raw, f)
		return path

	def custom_print(self, s, log=False):
		"""
		可以被monkey patch的print，在其他GUI上使用可以被替换为任何需要的输出
		打印信息和返回日志
		"""
		lg.info(s)
		if log:
			self.update_log += s + "\n"

	@staticmethod
	def get_cur_version(path):
		"""
		从MaaCore.dll获取当前版本号
		"""

		# 使用子进程获取当前版本后关闭，避免占用共享库。不这么做的话更新替换掉共享库文件后在退出程序会报段错误
		def _get_cur_version(path, result):
			Asst.load(path=path)
			result.put(Asst.get_version())

		result = multiprocessing.Queue()
		p = multiprocessing.Process(target=_get_cur_version, args=(path, result))
		p.start()
		p.join()
		return result.get()

	def __init__(self, path, incremental_path, version, proxies=None, system_platform="linux-x86_64"):
		self.custom_print("进入Update构造函数")
		self.path = path
		self.version = version
		self.latest_json = None
		self.latest_version = None
		self.assets_object = None
		self.proxies = proxies
		self.update_log = ""
		self.system_platform = system_platform
		self.custom_print("Asst.get_version 获取版本")
		self.cur_version = self.get_cur_version(path)
		self.custom_print(f"MAA当前版本 {self.cur_version}")

	@staticmethod
	def map_version_type(version):
		type_map = {Version.Nightly: "alpha", Version.Beta: "beta", Version.Stable: "stable"}
		return type_map.get(version, "stable")

	def get_latest_version(self, proxies=None):
		"""
		从API获取最新版本
		"""
		self.custom_print("从API获取最新版本信息")
		api_url = self.Mirrors
		version_summary = self.Summary_json
		retry = 3
		for retry_times in range(retry):
			# 在重试次数限制内依次请求每一个镜像
			i = retry_times % len(api_url)
			request_url = api_url[i] + version_summary
			try:
				response_data = requests.get(request_url, proxies=proxies, verify=False).json()
				"""
				解析JSON
				e.g.
				{
				  "alpha": {
					"version": "v4.24.0-beta.1.d006.g27dee653d",
					"detail": "https://ota.maa.plus/MaaAssistantArknights/api/version/alpha.json"
				  },
				  "beta": {
					"version": "v4.24.0-beta.1",
					"detail": "https://ota.maa.plus/MaaAssistantArknights/api/version/beta.json"
				  },
				  "stable": {
					"version": "v4.23.3",
					"detail": "https://ota.maa.plus/MaaAssistantArknights/api/version/stable.json"
				  }
				}
				"""
				version_type = self.map_version_type(self.version)
				latest_version = response_data[version_type]["version"]
				version_detail = response_data[version_type]["detail"]
				return latest_version, version_detail
			except Exception as e:
				self.custom_print(e)
				continue
		return False, False

	def get_download_url(self, detail):
		"""
		1.获取系统及架构信息
		2.找到对应的版本
		3.返回镜像url列表&文件名
		"""
		"""
		获取系统信息，包括：
			架构：ARM、x86
			系统：Linux、Windows
		默认Windows x86_64
		"""

		system = platform.system()
		if system == "Linux":
			machine = platform.machine()
			if machine == "aarch64":
				# Linux aarch64
				system_platform = "linux-aarch64"
			else:
				# Linux x86
				system_platform = "linux-x86_64"
		elif system == "Windows":
			machine = platform.machine()
			if machine == "AMD64" or machine == "x86_64":
				# Windows x86-64
				system_platform = "win-x64"
			else:
				# Windows ARM64
				system_platform = "win-arm64"
		# 请求的是https://ota.maa.plus/MaaAssistantArknights/api/version/stable.json，或其他版本类型对应的url
		detail_data = requests.get(detail, proxies=self.proxies, verify=False).json()
		assets_list = detail_data["details"]["assets"]  # 列表，子元素为字典
		changelog = detail_data["details"]["body"]  # 列表，子元素为字典
		# 找到对应系统和架构的版本
		for assets in assets_list:
			"""
			结构示例
			assets:
			{
				"name": "MAA-v4.24.0-beta.1.d006.g27dee653d-win-x64.zip",
				"size": 145677836,
				"browser_download_url": "https://github.com/MaaAssistantArknights/MaaRelease/releases/download/v4.24.0-beta.1.d006.g27dee653d/MAA-v4.24.0-beta.1.d006.g27dee653d-win-x64.zip",
				"mirrors": [
				  "https://s3.maa-org.net:25240/maa-release/MaaAssistantArknights/MaaRelease/releases/download/v4.24.0-beta.1.d006.g27dee653d/MAA-v4.24.0-beta.1.d006.g27dee653d-win-x64.zip",
				  "https://agent.imgg.dev/MaaAssistantArknights/MaaRelease/releases/download/v4.24.0-beta.1.d006.g27dee653d/MAA-v4.24.0-beta.1.d006.g27dee653d-win-x64.zip",
				  "https://maa.r2.imgg.dev/MaaAssistantArknights/MaaRelease/releases/download/v4.24.0-beta.1.d006.g27dee653d/MAA-v4.24.0-beta.1.d006.g27dee653d-win-x64.zip"
				]
			}
			"""
			assets_name = assets["name"]  # 示例值:MAA-v4.24.0-beta.1-win-arm64.zip
			# 正则匹配（用于选择当前系统及架构的版本）
			#
			pattern = r"^MAA-.*" + re.escape(system_platform) + r".*(gz|zip)"
			match = re.match(pattern, assets_name)
			if match:
				# Mirrors镜像列表
				mirrors = assets["mirrors"]
				github_url = assets["browser_download_url"]
				# 加上GitHub的release链接
				mirrors.insert(0, github_url)
				return mirrors, assets_name, github_url, changelog
		return False, False, "", ""

	def update(self):
		"""
		主函数
		"""
		self.custom_print("进入update主函数")
		do_updated = False
		do_OTA = False
		# 从dll获取MAA的版本
		current_version = self.cur_version
		# 从API获取最新版本
		# latest_version：版本号; version_detail：对应的json地址
		latest_version, version_detail = self.get_latest_version()
		self.custom_print("MaaAssistantArknights", log=True)
		self.custom_print(f"最新版本：{latest_version}", log=True)
		self.custom_print(f"当前版本：{current_version}", log=True)
		if not latest_version:  # latest_version为False代表获取失败
			self.custom_print("获取版本信息失败", log=True)
		elif current_version == latest_version:  # 通过比较二者是否一致判断是否需要更新
			self.custom_print("当前为最新版本，无需更新", log=True)
		else:
			self.custom_print("检测到版本差异", log=True)
			# 开始更新逻辑
			# 解析version_detail的JSON信息
			# 通过API获取下载地址列表和对应文件名
			url_list, filename, github_url, changelog = self.get_download_url(version_detail)
			version_log = changelog.replace("\\n" * 2, "\n").replace("\\n", "\n")
			self.custom_print(f"版本更新主要日志如下：\n{version_log}", log=True)
			self.custom_print("开始下载更新...", log=True)
			if not url_list:
				# 如果请求失败则返回False
				# （此返回值可能会在非Windows-x86_64的程序更新alpha版时出现）
				self.custom_print("未找到适用于当前系统的更新包", log=True)
				# 直接结束
				return
			# 将路径和文件名拼合成绝对路径
			# 默认在maa主程序/MaaCore.dll所在路径下
			file = os.path.join(self.path, filename)
			# 下载，调用Downloader下载器，使用url_list（镜像url列表）和file（文件保存路径）两个参数
			# 重试10次
			max_retry = 10
			for retry_frequency in range(max_retry):
				try:
					self.custom_print("开始下载" + (f"，第{retry_frequency}次尝试" if retry_frequency > 1 else ""))
					# 强制使用github_url，不从镜像源获取
					self.download_file(github_url, file)
					self.custom_print(f"新版本下载完成，压缩包大小约为{round((os.path.getsize(file))/1024/1024,1)}MB", log=True)
					# 解压下载的文件，
					self.custom_print("开始解压数据", log=True)
					file_extension = os.path.splitext(filename)[1]
					unzip = False
					# 根据拓展名选择解压算法
					# .zip(Windows)/.tar.gz(Linux)
					if file_extension == ".zip":
						zfile = zipfile.ZipFile(file, "r")
						zfile.extractall(self.path)
						zfile.close()
						unzip = True
						# 删除压缩包
						os.remove(file)
					# .tar.gz拓展名的情况（按照这个方式得到的拓展名是.gz，但是解压的是tar.gz
					elif file_extension == ".gz":
						tfile = tarfile.open(file, "r:gz")
						tfile.extractall(self.path)
						tfile.close()
						unzip = True
						# 删除压缩包
						os.remove(file)
					if unzip:
						self.custom_print("更新完成", log=True)
						do_updated = True
					else:
						self.custom_print("解压过程出现异常", log=True)
					break
				except Exception as e:
					lg.exception("下载过程出现异常")
					self.custom_print(str(e))
					if retry_frequency >= 9:
						self.custom_print("下载失败超过十次，放弃更新", log=True)

		self.custom_print("尝试获取OTA热更新资源", log=True)
		response = requests.get(self.ota_tasks_url, proxies=self.proxies, verify=False)
		ota_tasks_json = response.json()
		ota_tasks_path = self.path / "cache" / "resource" / "tasks.json"
		ota_tasks_bak_path = self.path / "cache" / "resource" / "tasks_bak.json"
		ota_tasks_path.parent.mkdir(parents=True, exist_ok=True)
		if os.path.exists(ota_tasks_bak_path):
			with open(ota_tasks_bak_path, "r", encoding="utf-8") as f:
				file_tasks_json = json.load(f)
				if ota_tasks_json == file_tasks_json:
					self.custom_print("OTA热更新资源无变化")
					return do_updated, do_OTA, self.update_log
		with open(ota_tasks_path, "w", encoding="utf-8") as f:
			with open(ota_tasks_bak_path, "w", encoding="utf-8") as f_bak:
				response = requests.get(self.ota_tasks_url, proxies=self.proxies, verify=False)
				task = ""
				added_key = []
				for key in response.json():
					task += key + "、"
					added_key.append(key)
				do_OTA = True
				self.custom_print(f"获取到信息：{task[:-1]}")
				f.write(response.text)
				f_bak.write(response.text)
		return do_updated, do_OTA, self.update_log

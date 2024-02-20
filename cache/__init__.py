import json
import os
import threading
from pathlib import Path

from _global import global_var

lock = threading.Lock()
cache_path = str(Path(__file__).parent)


def save_cache():
	with lock:
		with open(cache_path + "/cache.json", "w", encoding="utf8") as file:
			cache = {"tasks_config_waiting_queue": list(global_var.get("tasks_config_waiting_queue").queue), "send_msg_waiting_queue": list(global_var.get("send_msg_waiting_queue").queue), "interrupt_tasks_waiting_queue": list(global_var.get("interrupt_tasks_waiting_queue").queue)}
			file.write(json.dumps(cache, ensure_ascii=False, indent=4, separators=(", ", ": ")))


def read_cache():
	try:
		with open(cache_path + "/cache.json", "r", encoding="utf8") as file:
			try:
				cache = json.load(file)
			except ValueError:
				with global_var.get("tasks_config_waiting_queue").mutex:
					global_var.get("tasks_config_waiting_queue").queue.clear()
				with global_var.get("send_msg_waiting_queue").mutex:
					global_var.get("send_msg_waiting_queue").queue.clear()
				with global_var.get("interrupt_tasks_waiting_queue").mutex:
					global_var.get("interrupt_tasks_waiting_queue").queue.clear()
				return
			for item in cache["send_msg_waiting_queue"]:
				global_var.get("send_msg_waiting_queue").put(item)
			for item in cache["tasks_config_waiting_queue"]:
				global_var.get("tasks_config_waiting_queue").put(item)
			for item in cache["interrupt_tasks_waiting_queue"]:
				global_var.get("interrupt_tasks_waiting_queue").put(item)
	except FileNotFoundError:
		os.mknod(cache_path + "/cache.json")
		read_cache()

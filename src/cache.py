from collections import deque
from pathlib import Path
from src._global import TaskConfig
import orjson as json
import os
from loguru import logger as lg

def 导出_cache(	待执行的一般任务队列: deque[TaskConfig],
				待执行的中断任务队列: deque[TaskConfig]):
	with open(str(Path(__file__).parent.parent) + "/data/cache.json", "w", encoding="utf-8") as file:
		cache = {
				"待执行的一般任务队列": list(待执行的一般任务队列),
				"待执行的中断任务队列": list(待执行的中断任务队列),
				}
		file.write(json.dumps(cache).decode())

def 读取cache(	待执行的一般任务队列: deque[TaskConfig],
				待执行的中断任务队列: deque[TaskConfig]):
	file_path = str(Path(__file__).parent.parent) + "/data/cache.json"
	if not os.path.exists(file_path):
		导出_cache(待执行的一般任务队列, 待执行的中断任务队列)
		return
	with open(file_path, "r", encoding="utf-8") as file:
			try:
				cache = json.loads(file.read())
				for item in cache['待执行的一般任务队列']:
					待执行的一般任务队列.append(item)
				for item in cache['待执行的中断任务队列']:
					待执行的中断任务队列.append(item)
			except Exception:
				lg.exception("读取cache文件时出现错误")

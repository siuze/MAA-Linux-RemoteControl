from collections import deque
from pathlib import Path
from src._global import TaskConfig
import orjson as json
import os
import shutil
from loguru import logger as lg


def 导出_cache(待执行的一般任务队列: deque[TaskConfig], 待执行的中断任务队列: deque[TaskConfig]) -> None:
	"""
	原子化导出任务缓存文件。
	先写入临时文件，再通过 os.replace 进行原子替换，避免并发冲突或断电导致的 JSON 文件损坏。
	"""
	data_dir = Path(__file__).parent.parent / "data"
	data_dir.mkdir(parents=True, exist_ok=True)
	target_path = data_dir / "cache.json"
	tmp_path = data_dir / "cache.json.tmp"

	try:
		cache = {
			"待执行的一般任务队列": list(待执行的一般任务队列),
			"待执行的中断任务队列": list(待执行的中断任务队列),
		}
		raw_bytes = json.dumps(cache, option=json.OPT_INDENT_2)
		with open(tmp_path, "wb") as f:
			f.write(raw_bytes)
			f.flush()
			os.fsync(f.fileno())
		os.replace(tmp_path, target_path)
	except Exception as e:
		lg.exception(f"导出 cache 发生错误: {e!r}")
		if tmp_path.exists():
			try:
				tmp_path.unlink()
			except Exception:
				pass


def 读取cache(待执行的一般任务队列: deque[TaskConfig], 待执行的中断任务队列: deque[TaskConfig]) -> None:
	"""
	从缓存文件中恢复未完成的任务配置队列。
	若文件损坏，自动备份为 corrupt 文件，防止程序崩溃。
	"""
	file_path = Path(__file__).parent.parent / "data/cache.json"
	if not file_path.exists():
		导出_cache(待执行的一般任务队列, 待执行的中断任务队列)
		return

	try:
		with open(file_path, "rb") as file:
			content = file.read().strip()
			if not content:
				return
			cache = json.loads(content)
			for item in cache.get("待执行的一般任务队列", []):
				待执行的一般任务队列.append(item)
			for item in cache.get("待执行的中断任务队列", []):
				待执行的中断任务队列.append(item)
			lg.info(f"成功恢复缓存任务: 一般任务 {len(cache.get('待执行的一般任务队列', []))} 条, 中断任务 {len(cache.get('待执行的中断任务队列', []))} 条")
	except Exception as e:
		lg.exception(f"读取 cache 文件时出现错误，尝试备份损坏文件: {e!r}")
		try:
			bak_path = file_path.with_suffix(".corrupt.json")
			shutil.copyfile(file_path, bak_path)
		except Exception:
			pass

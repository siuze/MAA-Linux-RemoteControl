import gc
from src._global import TaskConfig
from collections import deque
from multiprocessing.queues import Queue as QUEUE
from queue import Empty
from multiprocessing.synchronize import Semaphore
from src.cache import 导出_cache
from loguru import logger as lg

class SyncQueue:
	def __init__(self,
				信号量: Semaphore,
				WS待执行的一般任务队列: QUEUE[TaskConfig],
				WS待执行的中断任务队列: QUEUE[TaskConfig],
				MAA待执行的一般任务队列: deque[TaskConfig],
				MAA待执行的中断任务队列: deque[TaskConfig],
				) -> None:
		self.信号量 = 信号量
		self.WS待执行的一般任务队列 = WS待执行的一般任务队列
		self.WS待执行的中断任务队列 = WS待执行的中断任务队列
		self.MAA待执行的一般任务队列 = MAA待执行的一般任务队列
		self.MAA待执行的中断任务队列 = MAA待执行的中断任务队列
	def run(self):
		while True:
			if self.信号量.acquire():
				try:
					self.MAA待执行的一般任务队列.append(self.WS待执行的一般任务队列.get(timeout=2))
					导出_cache(self.MAA待执行的一般任务队列, self.MAA待执行的中断任务队列)
					lg.info('SyncQueue MAA待执行的一般任务队列 增加一个配置')
					gc.collect()
				except Empty:
					pass
				try:
					self.MAA待执行的中断任务队列.append(self.WS待执行的中断任务队列.get(timeout=2))
					导出_cache(self.MAA待执行的一般任务队列, self.MAA待执行的中断任务队列)
					lg.info('SyncQueue MAA待执行的中断任务队列 增加一个配置')
					gc.collect()
				except Empty:
					pass

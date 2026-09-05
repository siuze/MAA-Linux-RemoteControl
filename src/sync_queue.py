import gc
import threading
from collections import deque
from multiprocessing.queues import Queue as QUEUE
from multiprocessing.synchronize import Semaphore
from queue import Empty
from loguru import logger as lg
from src._global import TaskConfig
from src.cache import 导出_cache


class SyncQueue:
	def __init__(
		self,
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
		self._stop_event = threading.Event()

	def stop(self) -> None:
		"""通知同步线程优雅退出"""
		self._stop_event.set()
		# 释放一次信号量以唤醒阻塞在 acquire 的线程
		try:
			self.信号量.release()
		except Exception:
			pass

	def run(self) -> None:
		while not self._stop_event.is_set():
			# 带有超时的 acquire，既保证高响应又支持 stop_event 优雅退出
			acquired = self.信号量.acquire(timeout=0.5)
			if not acquired:
				continue
			if self._stop_event.is_set():
				break

			has_change = False

			# 优先拉取中断任务（使用非阻塞 get_nowait，彻底消除 2 秒超时硬等）
			while True:
				try:
					item = self.WS待执行的中断任务队列.get_nowait()
					self.MAA待执行的中断任务队列.append(item)
					lg.info(f"SyncQueue 中断队列同步入队一条配置: 【{item.get('id', '')}】")
					has_change = True
				except Empty:
					break

			# 紧接着拉取一般任务
			while True:
				try:
					item = self.WS待执行的一般任务队列.get_nowait()
					self.MAA待执行的一般任务队列.append(item)
					lg.info(f"SyncQueue 一般队列同步入队一条配置: 【{item.get('id', '')}】")
					has_change = True
				except Empty:
					break

			if has_change:
				导出_cache(self.MAA待执行的一般任务队列, self.MAA待执行的中断任务队列)
				gc.collect()

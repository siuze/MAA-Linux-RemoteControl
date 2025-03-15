from collections import deque
import gc
import multiprocessing
import os
import threading
import time
from pathlib import Path
from multiprocessing import Process
from src.cache import 读取cache
from loguru import logger as lg
from src.ws import WS
from src.sync_queue import SyncQueue
from src.maa import MAA
from multiprocessing import Semaphore
from multiprocessing.synchronize import Semaphore as SemaphoreType
from multiprocessing import Queue
from multiprocessing.queues import Queue as QUEUE
from src._global import Notice, TaskConfig

lg.add(str(Path(__file__).parent / f"logs/log_{time.strftime('%Y-%m-%d', time.localtime()) }.log"), rotation="1 day", retention="15 days")


def WS数据收发进程(信号量: SemaphoreType,
				待执行的一般任务队列: QUEUE[TaskConfig],
				待执行的中断任务队列: QUEUE[TaskConfig],
				待发送的消息队列: QUEUE[Notice],):
	ws_app = WS(信号量,待执行的一般任务队列,待执行的中断任务队列,待发送的消息队列,)
	ws_app.run()

def MAA执行进程(信号量: SemaphoreType,
				待执行的一般任务队列: QUEUE[TaskConfig],
				待执行的中断任务队列: QUEUE[TaskConfig],
				待发送的消息队列: QUEUE[Notice],):
	lock = threading.Lock()
	MAA待执行的一般任务队列: deque[TaskConfig] = deque()
	MAA待执行的中断任务队列: deque[TaskConfig] = deque()
	读取cache(MAA待执行的一般任务队列,MAA待执行的中断任务队列)
	sync_queue = SyncQueue(信号量,待执行的一般任务队列,待执行的中断任务队列,MAA待执行的一般任务队列,MAA待执行的中断任务队列)
	maa = MAA()

	def 处理一般任务():
		while True:
			if len(MAA待执行的一般任务队列):
				if not maa.inited:
					lg.info("maa  执行初始化")
					lock.acquire()
					maa.init(MAA待执行的一般任务队列,MAA待执行的中断任务队列,待发送的消息队列)
					lock.release()
				config = MAA待执行的一般任务队列.popleft()
				lg.info("准备传入一个一般任务配置")
				maa.执行一般任务配置(config)
				gc.collect()
			time.sleep(1)
	def 处理中断任务():
		while True:
			if len(MAA待执行的中断任务队列):
				if not maa.inited:
					lg.info("maa执行初始化")
					lock.acquire()
					maa.init(MAA待执行的一般任务队列,MAA待执行的中断任务队列,待发送的消息队列)
					lock.release()
				config = MAA待执行的中断任务队列.popleft()
				lg.info("准备传入一个中断任务配置")
				maa.执行中断任务配置(config)
				gc.collect()
			time.sleep(1)
	t1 = threading.Thread(target=sync_queue.run)
	t2 = threading.Thread(target=处理一般任务)
	t3 = threading.Thread(target=处理中断任务)
	t1.start()
	t2.start()
	t3.start()
	空闲时间 = 0
	while True:
		time.sleep(30)
		if (maa.inited
			and len(MAA待执行的一般任务队列) == 0
			and len(MAA待执行的中断任务队列) == 0
			and not maa.maa.running()
			):
			空闲时间+= 30
			lg.info(f"{空闲时间=}")
		else:
			空闲时间 = 0
		if 空闲时间 > 600:
			lg.info("长时间没有任务，退出子进程以清理内存")
			os._exit(0)

	t1.join()
	t2.join()
	t3.join()


	


if __name__ == '__main__':
	multiprocessing.set_start_method('spawn')
	信号量 = Semaphore(0)
	待执行的一般任务队列: QUEUE[TaskConfig] = Queue()
	待执行的中断任务队列: QUEUE[TaskConfig] = Queue()
	待发送的消息队列: QUEUE[Notice] = Queue()
	p1 = Process(target=WS数据收发进程, args=(信号量,待执行的一般任务队列,待执行的中断任务队列,待发送的消息队列),daemon=False)
	p2 = Process(target=MAA执行进程, args=(信号量,待执行的一般任务队列,待执行的中断任务队列,待发送的消息队列),daemon=False)
	p1.start()
	p2.start()
	while True:
		if not p1.is_alive():
			lg.info("WS数据收发进程 退出，准备重启")
			try:
				p1.close()
			except Exception as e:
				lg.error(f"WS数据收发进程 清理失败 {e!r}")
			p1 = Process(target=WS数据收发进程, args=(信号量,待执行的一般任务队列,待执行的中断任务队列,待发送的消息队列),daemon=False)
			p1.start()
		if not p2.is_alive():
			lg.info("MAA执行进程 退出，准备重启")
			try:
				p2.close()
			except Exception as e:
				lg.error(f"MAA执行进程 清理失败 {e!r}")
			p2 = Process(target=MAA执行进程, args=(信号量,待执行的一般任务队列,待执行的中断任务队列,待发送的消息队列),daemon=False)
			p2.start()
		time.sleep(1)

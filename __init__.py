from collections import deque
import gc
import multiprocessing
from multiprocessing import Process, Queue, Semaphore
from multiprocessing.queues import Queue as QUEUE
from multiprocessing.synchronize import Semaphore as SemaphoreType
from pathlib import Path
import signal
import sys
import threading
import time
from typing import Any

from loguru import logger as lg
from src._global import Notice, TaskConfig
from src.cache import 读取cache
from src.maa import MAA, MaaRestartRequest
from src.process_utils import set_pdeathsig
from src.sync_queue import SyncQueue
from src.ws import WS

logs_dir = Path(__file__).parent / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
lg.add(
	str(logs_dir / f"log_{time.strftime('%Y-%m-%d', time.localtime())}.log"),
	rotation="1 day",
	retention="15 days",
)


def WS数据收发进程(
	信号量: SemaphoreType,
	待执行的一般任务队列: QUEUE[TaskConfig],
	待执行的中断任务队列: QUEUE[TaskConfig],
	待发送的消息队列: QUEUE[Notice],
) -> None:
	"""WebSocket 通信子进程，负责与服务端保持双向消息交互"""
	# Linux 环境绑定父进程死亡信号，防止主进程异常退出后变成孤儿
	set_pdeathsig(signal.SIGTERM)
	try:
		ws_app = WS(
			信号量,
			待执行的一般任务队列,
			待执行的中断任务队列,
			待发送的消息队列,
		)
		ws_app.run()
	except KeyboardInterrupt:
		pass
	except Exception as e:
		lg.exception(f"WS数据收发进程 异常退出: {e!r}")


def MAA执行进程(
	信号量: SemaphoreType,
	待执行的一般任务队列: QUEUE[TaskConfig],
	待执行的中断任务队列: QUEUE[TaskConfig],
	待发送的消息队列: QUEUE[Notice],
) -> None:
	"""MAA 执行子进程，隔离运行 libMaaCore 动态库与 ADB 交互"""
	set_pdeathsig(signal.SIGTERM)
	lock = threading.Lock()
	stop_worker = threading.Event()

	MAA待执行的一般任务队列: deque[TaskConfig] = deque()
	MAA待执行的中断任务队列: deque[TaskConfig] = deque()
	读取cache(MAA待执行的一般任务队列, MAA待执行的中断任务队列)

	sync_queue = SyncQueue(
		信号量,
		待执行的一般任务队列,
		待执行的中断任务队列,
		MAA待执行的一般任务队列,
		MAA待执行的中断任务队列,
	)
	maa = MAA()

	def 处理一般任务() -> None:
		while not stop_worker.is_set():
			if len(MAA待执行的一般任务队列):
				lg.info("准备执行一个一般任务配置")
				if not maa.inited:
					lg.info("MAA 执行初始化")
					with lock:
						maa.init(MAA待执行的一般任务队列, MAA待执行的中断任务队列, 待发送的消息队列)
				config = MAA待执行的一般任务队列.popleft()
				lg.info(f"准备传入一般任务配置: 【{config.get('id')}】")
				try:
					maa.执行一般任务配置(config)
				except MaaRestartRequest:
					stop_worker.set()
					break
				except Exception as e:
					lg.exception(f"执行一般任务配置异常: {e!r}")
				finally:
					gc.collect()
			time.sleep(1)

	def 处理中断任务() -> None:
		while not stop_worker.is_set():
			if len(MAA待执行的中断任务队列):
				if not maa.inited:
					lg.info("MAA 执行初始化")
					with lock:
						maa.init(MAA待执行的一般任务队列, MAA待执行的中断任务队列, 待发送的消息队列)
				config = MAA待执行的中断任务队列.popleft()
				lg.info(f"准备传入中断任务配置: 【{config.get('id')}】")
				try:
					maa.执行中断任务配置(config)
				except MaaRestartRequest:
					stop_worker.set()
					break
				except Exception as e:
					lg.exception(f"执行中断任务配置异常: {e!r}")
				finally:
					gc.collect()
			time.sleep(1)

	t1 = threading.Thread(target=sync_queue.run, daemon=True)
	t2 = threading.Thread(target=处理一般任务, daemon=True)
	t3 = threading.Thread(target=处理中断任务, daemon=True)
	t1.start()
	t2.start()
	t3.start()

	空闲时间 = 0
	try:
		while not stop_worker.is_set():
			time.sleep(10)
			if stop_worker.is_set():
				break

			# 检查是否满足空闲休眠条件
			is_idle = (
				maa.inited
				and len(MAA待执行的一般任务队列) == 0
				and len(MAA待执行的中断任务队列) == 0
				and (maa.maa is None or not maa.maa.running())
			)
			if is_idle:
				空闲时间 += 10
				if 空闲时间 % 60 == 0:
					lg.info(f"MAA当前处于空闲状态，累计空闲时间: {空闲时间}s")
			else:
				空闲时间 = 0

			if 空闲时间 >= 600:
				lg.info("空闲超过 10 分钟，执行优雅休眠并退出子进程以彻底释放 C++ 内存")
				stop_worker.set()
				break
	except KeyboardInterrupt:
		stop_worker.set()
	finally:
		lg.info("MAA 执行进程开始优雅反初始化清理...")
		sync_queue.stop()
		maa.destroy()
		# 安全回收子线程
		t2.join(timeout=2.0)
		t3.join(timeout=2.0)
		t1.join(timeout=1.0)
		lg.info("MAA 执行进程资源已彻底释放，正常终止退出")
		sys.exit(0)


def safely_recycle_process(p: Process, name: str) -> None:
	"""
	安全回收子进程，严防僵尸进程 (defunct) 残留。
	先调用 join 回收，超时则发送 terminate 并强制回收内核 PCB。
	"""
	if p is None:
		return
	try:
		p.join(timeout=2.0)
		if p.is_alive():
			lg.warning(f"子进程 {name} 未能在 2s 内退出，发送 terminate 信号")
			p.terminate()
			p.join(timeout=2.0)
		if p.is_alive():
			lg.warning(f"子进程 {name} terminate 超时，发送 kill 强杀")
			p.kill()
			p.join(timeout=1.0)
	except Exception as e:
		lg.error(f"回收子进程 {name} 发生异常: {e!r}")
	finally:
		try:
			p.close()
		except Exception:
			pass


def main() -> None:
	if multiprocessing.get_start_method(allow_none=True) != "spawn":
		try:
			multiprocessing.set_start_method("spawn")
		except RuntimeError:
			multiprocessing.set_start_method("spawn", force=True)
	信号量 = Semaphore(0)
	待执行的一般任务队列: QUEUE[TaskConfig] = Queue()
	待执行的中断任务队列: QUEUE[TaskConfig] = Queue()
	待发送的消息队列: QUEUE[Notice] = Queue()

	p1 = Process(
		target=WS数据收发进程,
		args=(信号量, 待执行的一般任务队列, 待执行的中断任务队列, 待发送的消息队列),
		daemon=False,
	)
	p2 = Process(
		target=MAA执行进程,
		args=(信号量, 待执行的一般任务队列, 待执行的中断任务队列, 待发送的消息队列),
		daemon=False,
	)

	running = True

	def on_signal(signum: int, frame: Any) -> None:
		nonlocal running
		lg.info(f"主进程接收到信号 {signum}，准备优雅终止所有子进程...")
		running = False

	signal.signal(signal.SIGINT, on_signal)
	signal.signal(signal.SIGTERM, on_signal)

	p1.start()
	p2.start()
	lg.info(f"MAA-LRC 主守护进程启动成功，WS进程 PID={p1.pid}, MAA进程 PID={p2.pid}")

	while running:
		if not p1.is_alive():
			lg.info("WS数据收发进程 退出，安全回收并重新拉起")
			safely_recycle_process(p1, "WS数据收发进程")
			p1 = Process(
				target=WS数据收发进程,
				args=(信号量, 待执行的一般任务队列, 待执行的中断任务队列, 待发送的消息队列),
				daemon=False,
			)
			p1.start()

		if not p2.is_alive():
			lg.info("MAA执行进程 退出，安全回收并重新拉起")
			safely_recycle_process(p2, "MAA执行进程")
			p2 = Process(
				target=MAA执行进程,
				args=(信号量, 待执行的一般任务队列, 待执行的中断任务队列, 待发送的消息队列),
				daemon=False,
			)
			p2.start()

		time.sleep(1)

	# 主进程退出时的级联清理
	lg.info("正在执行主守护进程退出清理...")
	safely_recycle_process(p1, "WS数据收发进程")
	safely_recycle_process(p2, "MAA执行进程")
	lg.info("所有子进程已完整回收，主守护进程退出")


if __name__ == "__main__":
	main()

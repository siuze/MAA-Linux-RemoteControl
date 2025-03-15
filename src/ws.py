import gc
import threading
import time
from multiprocessing.queues import Queue as QUEUE
from pathlib import Path

import orjson as json
import yaml
from loguru import logger as lg
from websocket import WebSocket, WebSocketApp
from multiprocessing.synchronize import Semaphore

from src._global import Notice, TaskConfig


class WS:
	
	def __init__(self,
				信号量: Semaphore,
				待执行的一般任务队列: QUEUE[TaskConfig],
				待执行的中断任务队列: QUEUE[TaskConfig],
				待发送的消息队列: QUEUE[Notice],
				):
		self.信号量 = 信号量
		self.待执行的一般任务队列: QUEUE[TaskConfig] = 待执行的一般任务队列
		self.待执行的中断任务队列: QUEUE[TaskConfig] = 待执行的中断任务队列
		self.待发送的消息队列: QUEUE[Notice] = 待发送的消息队列

	def on_open(self, wsapp:WebSocket):
		lg.info("MAA成功连接到WS服务端")

		def check_and_send_message():
			try:
				while True:
					msg = json.dumps(self.待发送的消息队列.get()).decode()
					lg.info(f"准备发送消息 {msg[:500]}")
					wsapp.send(msg)
					gc.collect()
			except Exception as e:
				lg.error(f"{e!r} 消息发送模块出现异常，退出")

		threading.Thread(target=check_and_send_message).start()

	def on_message(self, wsapp:WebSocket, msg: str):
		lg.info("收到WS消息:")
		lg.info(msg)
		try:
			config:TaskConfig = json.loads(msg)
		except ValueError:
			self.待发送的消息队列.put(
				{"type": "receipt",
	 			"status": "FAILED",
				"payload": "收到的消息无法以json格式解析"})
			return
		try:
			if config["type"] == "interrupt":
				self.待执行的中断任务队列.put(config)
			else:
				self.待执行的一般任务队列.put(config)
			self.待发送的消息队列.put(
				{"type": "receipt",
				"status": "SUCCESS",
				"payload": f"MAA已收到一条 {config["type"]} 任务配置：【{config['id']}】，加入队列等待运行",})
			self.信号量.release()
		except Exception as e:
			lg.error(f"处理消息时出错 {e!r}")

	def on_error(self, wsapp:WebSocket, e: str):
		lg.error(f"WS连接出错 {e!r}")


	def on_close(self, wsapp:WebSocket, close_status_code: int, close_reason: str):
		lg.info(f"WS连接关闭 {close_status_code=} {close_reason=}")


	def run(self, ):
		with open(str(Path(__file__).parent.parent / "config.yaml"), "r", encoding="utf8") as config_f:
			ws_url = yaml.safe_load(config_f)["python"]["ws"]
		while True:
			try:
				wsapp = WebSocketApp(ws_url, on_open=self.on_open, on_message=self.on_message, on_error=self.on_error, on_close=self.on_close)
				try:
					wsapp.run_forever(ping_interval=10, ping_timeout=3) # type: ignore
				except KeyboardInterrupt:
					lg.error("检测到KeyboardInterrupt，准备5s后退出WS线程")
					time.sleep(5)
					try:
						wsapp.close() # type: ignore
					except Exception:
						pass
					exit()
			except Exception as e:
				lg.error(f"WS连接任务出现异常 {e!r} 5s后重连")
			finally:
				time.sleep(5)



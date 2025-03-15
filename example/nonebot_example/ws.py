from pathlib import Path
from nonebot import get_driver, logger
from nonebot.drivers import URL, WebSocket, WebSocketServerSetup
from nonebot.exception import WebSocketClosed
import json

import asyncio

# nonebot是服务端
# maa是客户端
# 只允许收发json格式文本
from .maa import handle_receive

ws_client = None


async def send_ws(msg: dict):
	global ws_client
	try:
		text = json.dumps(msg, ensure_ascii=False)
		await ws_client.send(text)
		return {"status": "success", "msg": "消息已推送"}
	except Exception as e:
		logger.exception("出现异常")
		return {"status": "failed", "msg": f"出现异常（{str(type(e).__name__)} {str(e)}）"}


async def send_scheduled_tasks():
	"""
	获取tasks文件夹下所有配置并按优先级顺序排列
	"""
	with open(Path(__file__).parent / "data/config.json") as f:
		tasks_config = json.load(f)
	for task_index in range(len(tasks_config)):
		logger.info(await send_ws(tasks_config[task_index]))
		await asyncio.sleep(2)


async def receive_ws(msg: dict):
	resp = await handle_receive(msg)
	if "action" in resp and resp["action"] == "reply":
		await send_ws(resp["msg"])


async def maa_ws_handler(ws: WebSocket):
	global ws_client
	await ws.accept()
	ws_client = ws
	if ws_client is not None:
		logger.info("来自MAA的WS连接成功")
	else:
		logger.warning("来自MAA的WS连接已存在，连接被替换")
		# await ws.close()
	try:
		while True:
			data = await ws.receive()
			logger.info(f"收到MAA的消息，消息长度{len(data)}")
			try:
				data = json.loads(data)
				text="消息内容如下：\n"
				for key,value in data.items():
					if key != 'image':
						text += f"{key}: {value}\n"
					else:
						text += f"{key}: {value[:50]}...{value[-50:]}\n"
				text = text[:-1]
				logger.info(text)
			except ValueError:
				text = json.dumps({"type": "reply", "msg": "收到的消息无法通过json格式化"}, ensure_ascii=False)
				await ws.send_text(text)
			await receive_ws(data)
	except WebSocketClosed as e:
		logger.warning("来自MAA的WS连接断开")
		logger.error(str(e))
		try:
			await ws.close()
		except Exception:
			pass
	except Exception:
		logger.exception("出现异常")



driver = get_driver()
driver.setup_websocket_server(
	WebSocketServerSetup(
		path=URL("/maa"),
		name="maa",
		handle_func=maa_ws_handler,
	)
)

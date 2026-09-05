import asyncio
import json
from pathlib import Path
from typing import Any

from nonebot import get_driver, logger
from nonebot.drivers import URL, WebSocket, WebSocketServerSetup
from nonebot.exception import WebSocketClosed

from .maa import handle_receive

ws_client: WebSocket | None = None


async def send_ws(msg: dict[str, Any]) -> dict[str, str]:
	"""向已连接的 MAA-LRC 客户端下发 JSON 格式的任务配置"""
	global ws_client
	if ws_client is None:
		logger.warning("当前无活跃的 MAA 客户端 WebSocket 连接，无法推送任务")
		return {"status": "failed", "msg": "客户端未连接"}
	try:
		text = json.dumps(msg, ensure_ascii=False)
		await ws_client.send(text)
		return {"status": "success", "msg": "任务配置已成功推送"}
	except Exception as e:
		logger.exception("向 MAA 客户端推送任务发生异常")
		return {"status": "failed", "msg": f"异常: {type(e).__name__} {e}"}


async def send_scheduled_tasks() -> None:
	"""
	读取 data/tasks_config.json 中的任务配置，并按顺序下发给客户端
	"""
	config_file = Path(__file__).parent / "data/tasks_config.json"
	if not config_file.exists():
		logger.error("未找到任务配置文件: %s", config_file)
		return

	try:
		with open(config_file, encoding="utf-8") as f:
			tasks_config = json.load(f)

		for task in tasks_config:
			res = await send_ws(task)
			logger.info("推送任务结果: %s", res)
			await asyncio.sleep(2)
	except Exception as e:
		logger.exception("执行定时任务推送时出现异常: %s", e)


async def receive_ws(msg: dict[str, Any]) -> None:
	"""处理客户端推送的通知报文"""
	resp = await handle_receive(msg)
	if resp and resp.get("action") == "reply" and "msg" in resp:
		await send_ws(resp["msg"])


async def maa_ws_handler(ws: WebSocket) -> None:
	"""MAA WebSocket 路由处理端点 (/maa)"""
	global ws_client
	await ws.accept()
	ws_client = ws
	logger.info("MAA-LRC 客户端 WebSocket 连接已建立")

	try:
		while True:
			data = await ws.receive()
			logger.info("收到来自 MAA 客户端的消息，长度: %d 字节", len(data))
			try:
				parsed_data = json.loads(data)
				# 过滤大体积 Base64 截图日志
				log_preview: dict[str, Any] = {}
				for key, value in parsed_data.items():
					if key == "image" and isinstance(value, str) and len(value) > 100:
						log_preview[key] = f"<Base64 image {len(value)} chars>"
					else:
						log_preview[key] = value
				logger.info("消息摘要: %s", log_preview)
			except ValueError:
				reply_text = json.dumps({"type": "reply", "msg": "收到的消息无法通过 JSON 格式化"}, ensure_ascii=False)
				await ws.send_text(reply_text)
				continue

			await receive_ws(parsed_data)

	except WebSocketClosed as e:
		logger.warning("来自 MAA 的 WebSocket 连接已正常关闭: %s", e)
	except Exception as e:
		logger.exception("MAA WebSocket 接收循环异常: %s", e)
	finally:
		if ws_client == ws:
			ws_client = None
		try:
			await ws.close()
		except Exception:
			pass


driver = get_driver()
driver.setup_websocket_server(
	WebSocketServerSetup(
		path=URL("/maa"),
		name="maa",
		handle_func=maa_ws_handler,
	)
)

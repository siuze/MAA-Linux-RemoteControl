import traceback
from nonebot import get_driver,logger
from nonebot.drivers import URL, ASGIMixin, WebSocket, WebSocketServerSetup
from nonebot.exception import WebSocketClosed
import json
from pathlib import Path
import asyncio
#nonebot是服务端
#maa是客户端
#只允许收发json格式文本
from .config import config
from .maa import handle_receive

ws_client = None



async def send_ws(msg:dict):
	global ws_client
	try:
		# if ws_client != None:
			text = json.dumps(msg, ensure_ascii=False)
			await ws_client.send(text)
			return {"status":"success","msg":"消息已推送"}
		# else:
			# return {"status":"failed","msg":"WS连接尚未建立"}
	except Exception as e:
		logger.error(traceback.format_exc())
		return {"status":"failed","msg":f"出现异常（{str(type(e).__name__)} {str(e)}）"}


async def send_scheduled_tasks(_task:str='', index:list=[], qq=None, schedule=False)->dict:
		"""
		获取tasks文件夹下所有配置并按优先级顺序排列
		"""
		tasks_config = config.get_tasks(_task)
		if _task == 'stop_config' and qq !=None:
			found = False
			for one_config in config.get_tasks(''):
				logger.info(one_config["qq"])
				logger.info(str(qq))
				logger.info(one_config["qq"] == str(qq))
				if one_config["qq"] == str(qq):
					tasks_config[0]['tasks'][0]['params']['name'] = one_config['name']
					found = True
					break
			if not found:
				logger.info(f"没有与该账号{qq}绑定的配置")
				return {'status':"error", 'msg': f"没有与该账号{qq}绑定的配置"}
		tasks_config = sorted(tasks_config, key=lambda x: x['priority'])
		for task_index in range(len(tasks_config)):
			if schedule and "delay" in tasks_config[task_index] and tasks_config[task_index]["delay"] > 0:
				logger.info("该配置设置了暂停执行，跳过")
				tasks_config[task_index]["delay"] -= 1
				config.set_tasks(tasks_config)
				continue
			if index == []:
				logger.info("未给定配置序号")
				if qq and "qq" in tasks_config[task_index]:
					
					if qq == tasks_config[task_index]['qq']:
						logger.info(await send_ws(tasks_config[task_index]))
				else:
					logger.info(await send_ws(tasks_config[task_index]))
			elif str(task_index) in index:
				if qq and "qq" in tasks_config[task_index]:
					if qq == tasks_config[task_index]['qq']:
						logger.info(f"发送配置{task_index}")
						logger.info(await send_ws(tasks_config[task_index]))
				else:
					logger.info(f"发送配置{task_index}")
					logger.info(await send_ws(tasks_config[task_index]))
			await asyncio.sleep(2)




async def receive_ws(msg:dict):
	resp = await handle_receive(msg)
	if 'action' in resp and resp['action'] == 'reply':
		await send_ws(resp['msg'])


async def maa_ws_handler(ws: WebSocket):
	global ws_client
	await ws.accept()
	ws_client = ws
	if ws_client != None:
		logger.info("来自MAA的WS连接成功")
	else:
		logger.warning("来自MAA的WS连接已存在，连接被替换")
		# await ws.close()
	try:
		while True:
			
			data = await ws.receive()
			logger.info(f"收到MAA的消息，消息长度{len(data)}")
			logger.info(data[:1000])
			try:
				data = json.loads(data)
			except ValueError:
				text = json.dumps({'type':'reply','msg':'收到的消息无法通过json格式化'}, ensure_ascii=False)
				await ws.send_text(text)
			await receive_ws(data)
	except WebSocketClosed as e:
		logger.warning("来自MAA的WS连接断开")
		logger.error(str(e))
		try:
			await ws.close()
		except:
			pass
	except Exception as e:
		logger.error(traceback.format_exc())
	# finally:
		# await ws.close()
		# ws_client = None



driver = get_driver()
driver.setup_websocket_server(
		WebSocketServerSetup(
			path=URL("/maa"),
			name="maa",
			handle_func=maa_ws_handler,
		)
	)
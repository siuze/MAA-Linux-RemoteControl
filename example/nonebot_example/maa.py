from nonebot import logger, Bot, get_bot
import base64
from 你所用的适配器 import Message, MessageSegment
from .typeddef import Notice
import asyncio


async def send_notice(msg_chain):
	logger.info("准备发送消息")
	bot: Bot = get_bot()
	await bot.send_group_msg(group_id=1234567, message=Message(msg_chain))

async def handle_receive(msg: Notice) -> dict:
	try:
		if msg["type"] in ("receipt","important_notice","'config_start'"):
			await send_notice(Message([MessageSegment(type="text", data={"text": msg["payload"]})]))

		elif msg["type"] == "update_log" and msg["status"] != "OK":
			update_log = msg["payload"]
			part_index = 0
			while part_index < len(update_log):
				await send_notice(Message([MessageSegment(type="text", data={"text": update_log[part_index:part_index+500]})]))
				part_index += 500
				await asyncio.sleep(5)

		elif msg["type"] == 'config_end' and 'config' in msg:
			await send_notice([MessageSegment(type="text", data={"text": f"配置 【{msg['config']['id']}】执行结束\n"}),MessageSegment.at(msg["config"]["qq"])])

		elif msg["type"] == "task_result" and 'config' in msg:
			config_task = msg["config"]['tasks'][0]
			text = f"【配置 {msg["config"]['id']} 】\n"
			text += f"【任务 {config_task['name']} 】"
			if "duration" in msg:
				text += f"\n耗时 {(int(msg['duration']))}s"
			if msg["status"] in ("SUCCESS",'OK'):
				text += "\n任务正常执行"
			elif msg["status"] == "FAILED":
				text += "\n任务执行失败或异常"
			if msg["payload"]:
				text += f"\n{msg['payload'][:1000]}"
			logger.info(text)
			msg_chain = [MessageSegment(type="text", data={"text": text})]
			if "image" in msg and msg["image"]:
				img_rb = base64.b64decode(msg["image"])
				msg_chain.append(MessageSegment.image(img_rb)))
			await send_notice(msg_chain)
		else:
			pass
		return {"status": "success"}
	except Exception as e:
		logger.error(str(type(e).__name__) + str(e))
		return {"status": "error", "msg": str(type(e).__name__) + str(e)}

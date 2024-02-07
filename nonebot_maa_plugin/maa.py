from nonebot import logger,Bot, get_bot
import traceback
import base64
from pathlib import Path
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from .utils import seconds_format, text_transform, png2jpg
from .config import config
import asyncio
merge_recall_list = []

async def send_notice(msg_chain):
	retry = 0
	while retry < 5:
		try:
			bot: Bot = get_bot()
			await bot.send_group_msg( group_id=config.get_config("notice_group_id"), message=Message(msg_chain))
			break
		except Exception as e:
			logger.error(traceback.format_exc())
			logger.info("出错，5秒后重试")
			retry += 1
			await asyncio.sleep(5)

async def append_merge_recall_list(msg):
	merge_recall_list.append({
				"type": "node",
				"data": {
					"name": "机器人的昵称",
					"uin": "机器人的QQ号",
					"content": msg
					}
				} )
	logger.info(f"merge_recall_list增加一条消息，现有{len(merge_recall_list)}条消息")
	if len(merge_recall_list) > 29:
			await send_merge_recall()

async def send_merge_recall():
	global merge_recall_list
	try:
		length = len(merge_recall_list)
		if config.get_config("maa_recall_enable"):
			logger.info(f"merge_recall_list准备发送{length}条消息")
			await asyncio.sleep(10)
			bot: Bot = get_bot()
			await bot.send_group_forward_msg(group_id = config.get_config("notice_group_id"), messages = merge_recall_list) 
		del merge_recall_list[0:length]
		logger.info(f"merge_recall_list清空旧消息，现有{len(merge_recall_list)}条消息")
	except Exception as e:
		logger.error(traceback.format_exc())
		# return {'status':'error', 'msg': str(type(e).__name__) + str(e)}
		logger.info("出错，5秒后重试")
		await asyncio.sleep(5)
		await send_merge_recall()


async def handle_receive(msg:dict)->dict:
	global merge_recall_list
	try:
		if msg['type'] == 'receipt' or msg['type'] == 'notice' :
			bot: Bot = get_bot()
			if config.get_config("maa_recall_enable"):
				await bot.send_group_msg( group_id=config.get_config("notice_group_id"), message=Message([MessageSegment(type="text", data={"text": text_transform(msg['payload'])})]))

		if msg['type'] == 'update_notice':
			if msg['status'] == "UPDATED":
				bot: Bot = get_bot()
				if config.get_config("maa_recall_enable"):
					await bot.send_group_msg( group_id=config.get_config("notice_group_id"), message=Message([MessageSegment(type="text", data={"text": text_transform(msg['payload'])})]))
					
		if msg['type'] == 'normal_config_notice':
			if msg['status'] == 'BEGIN':
				if len(merge_recall_list):
					await send_merge_recall()
				# merge_recall_list.clear()
				msg_chain = [MessageSegment(type="text", data={"text": text_transform(msg['payload'])})]
				await append_merge_recall_list(msg_chain)
				# await send_notice(msg_chain)
			elif msg['status'] == 'END':
				msg_chain = [MessageSegment(type="text", data={"text": text_transform(msg['payload'])})]
				await append_merge_recall_list(msg_chain)
				await send_merge_recall()
				
		if msg['type'] == 'normal_task_report' or msg['type'] == 'interrupt_task_report':
			text = f"【配置 {msg['name']} 】\n"
			text += f"【任务 {msg['task']} 】"
			if 'duration' in msg:
				text += f"\n耗时 {seconds_format(msg['duration'])}"
			if msg['status'] == 'SUCCESS':
				text += "\n任务执行成功"
			elif msg['status'] == 'FAILED':
				text += "\n任务执行失败或异常"
			if msg['payload']:
				text += f"\n{msg['payload'][:1000]}"
			logger.info(text)
			msg_chain = [MessageSegment(type="text", data={"text": text_transform(text)})]
			if "image" in msg and msg['image']:
				img_rb = base64.b64decode(msg['image'])
				with open(Path(__file__).parent / f'data/maa/img/{msg["task"]}.png','wb') as f:
					f.write(img_rb)
				msg_chain.append(MessageSegment.image(png2jpg(img_rb)))
			if (('notice' not in msg['task_config']) or msg['task_config']['notice']==True) and config.get_config("maa_recall_enable"):
				if config.get_config("recall_merge") and msg['type'] == 'normal_task_report':
					await append_merge_recall_list(msg_chain)
					if '!重要!' in msg['payload']:
						await send_notice(msg_chain)
				else:
					await send_notice(msg_chain)
		else:
			logger.info(msg)
		return {'status':'success'}
	except Exception as e:
		logger.error(traceback.format_exc())
		return {'status':'error', 'msg': str(type(e).__name__) + str(e)}



# async def get_screenshot()->dict:
	
 
 


async def send_update_task():
	config = {
		
	}

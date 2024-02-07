from typing import Any, Annotated
from nonebot import on_regex, logger, require, Bot, get_bot, get_driver
from nonebot.permission import SUPERUSER
from nonebot.params import RegexDict
from nonebot.exception import MatcherException
from nonebot.typing import T_State
from nonebot.params import EventMessage
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Message

__plugin_meta__ = PluginMetadata(
	name="MAA自动挂机",
	description="明日方舟MAA自动挂机",
	usage="",
	type="application",
	extra={'help':"""
		☞要想让插件运行，你至少需要修改：
			1. ./data/maa/config.json里面的notice_group_id
			2. ./maa.py里面的append_merge_recall_list函数下：机器人的昵称和机器人的QQ号
			3. ./data/maa/tasks_config.json 里面可以放置多个配置，相比MAA-LRC要求的配置写法，每个配置还必须多增加以下参数：
				"qq": 这个配置所绑定的QQ号；
				"priority": 优先级，如果一次下发多个配置，将会按照优先级排序，数字越小越先执行；
				"delay": 这个配置暂停执行的次数，会让定时任务执行时单独跳过这个配置数次，一般是用户用指令控制，默认填0。
				"tasks": [ { "notice": true   单独控制每个任务的通知是否要发到通知群里面。
			4. nonebot2的.env配置中 DRIVER=~fastapi 
			4. 把nonebot_maa_plugin文件夹放在nonebot2项目的plugins文件夹下，在启动相关的文件中引入插件，比如在bot.py中加入：nonebot.load_plugins("plugins")

		☞./data/maa/config.json配置文件说明：
			1. maa_schedule_enable 每天4,12,20整点会自动定时下发所有的任务配置给MAA-LRC
			2. recall_merge 为了防止通知消息过多打扰，会在一个配置里面的所有任务都完成后再以合并转发的形式发送一条消息到通知群，如果通知内容包含重要信息（日志中包含 !重要! 这个关键字，或者来自中断任务），则会无视这个配置直接单独发一条消息
			3. maa_recall_enable 是否允许发送来自MAA-LRC的通知消息到通知群里
			4. notice_group_id 来自MAA-LRC的通知消息将发送到这个群号为这个ID的群中
			5. maa_task_wait 临时暂停未来要定时执行的任务n次

		☞用户指令（超管当然也能用）：
		【maa启动】启动自己绑定的配置
		【maa停止】停止正在运行的或等待运行的自己的配置
		【maa暂停1】暂停1次未来的定时任务（不影响别人的）
		【maa配置】 修改用户自己的配置里面的任务。注意：这个功能只能修改已存在的配置里面的子任务。想要添加一整套新的配置、绑定新用户的功能还没写，目前还是要在后台修改json文件来实现
		【maa截图】
		☞超级管理员指令：
		【maa启动([0-9, ]+)?】启动所有配置，加/启动自己的
		【maa停止】停止所有配置，加/停止自己的
		【maa暂停[0-9]+】暂停所有人的定时任务n次
		【maa更新】
		【maa定时打开】【maa定时关闭】
		【maa通知打开】【maa通知关闭】
		"""},
)

from .ws import *
from .config import config


maa = on_regex(r"^((maa)|(MAA)|(Maa))\s?启动(?P<index>([0-9, ]+)?)$", 
						  permission=SUPERUSER,
						  priority=10, 
						  block=True
						  )

maa_update = on_regex(r"^/?((maa)|(MAA)|(Maa))\s?更新$", 
						  permission=SUPERUSER,
						  priority=101, 
						  block=True
						  )
maa_screenshot = on_regex(r"^/?((maa)|(MAA)|(Maa))\s?截图$", 
						#   permission=SUPERUSER,
						  priority=101, 
						  block=True
						  )
maa_stop = on_regex(r"^((maa)|(MAA)|(Maa))\s?停止$", 
						  permission=SUPERUSER,
						  priority=101, 
						  block=True
						  )
maa_stop_config = on_regex(r"^/?((maa)|(MAA)|(Maa))\s?停止当前(任务|配置)?$", 
						  permission=SUPERUSER,
						  priority=101, 
						  block=True
						  )
maa_schedule_ctrl = on_regex(r"^/?((maa)|(MAA)|(Maa))\s?定时(任务)?(?P<bool>(打开|开启|启动|关闭|停止))$", 
						  permission=SUPERUSER,
						  priority=101, 
						  block=True
						  )
maa_recall_ctrl = on_regex(r"^/?((maa)|(MAA)|(Maa))\s?(回调|通知|回调消息|通知消息|消息)(?P<bool>(打开|开启|启动|关闭|停止))$", 
						  permission=SUPERUSER,
						  priority=101, 
						  block=True
						  )
maa_schedule_delay = on_regex(r"^((maa)|(MAA)|(Maa))\s?(定时)?(任务)?(延迟|暂停|跳过)\s?(?P<wait>([0-9]+))$", 
						  permission=SUPERUSER,
						  priority=101, 
						  block=True
						  )
maa_config = on_regex(r"^/?((maa)|(MAA)|(Maa))\s?(修改)?配置$", 
						#   permission=SUPERUSER,
						  priority=101, 
						  block=True
						  )

maa_start_user = on_regex(r"^/?((maa)|(MAA)|(Maa))\s?启动$", 
						  priority=200, 
						  block=True
						  )
maa_stop_user = on_regex(r"^/?((maa)|(MAA)|(Maa))\s?(停止|关闭)$", 
						  priority=200, 
						  block=True
						  )
maa_schedule_delay_user = on_regex(r"^/?((maa)|(MAA)|(Maa))\s?(定时)?(任务)?(延迟|暂停|跳过)\s?(?P<wait>([0-9]+))$", 
						  priority=200, 
						  block=True
						  )




@maa_start_user.handle()
async def maa_start_user_handle(event):
	await send_scheduled_tasks(qq=str(event.get_user_id()))
@maa_stop_user.handle()
async def maa_stop_user_handle(event):
	await send_scheduled_tasks('stop_config',qq=str(event.get_user_id()))
@maa_schedule_delay_user.handle()
async def maa_schedule_delay_user_handle(event, match: Annotated[dict[str, Any], RegexDict()],):
	qq=str(event.get_user_id())
	all_config = config.get_tasks('')
	for index in range(len(all_config)):
		if qq == all_config[index]['qq']:
			all_config[index]['delay'] = int(match['wait'])
			config.set_tasks(all_config)
			await maa_schedule_delay.finish(f"已将{qq}所绑定的配置设定为：暂停执行下未来{(match['wait'])}次MAA定时任务", reply_message=True, at_sender=False )
	await maa_schedule_delay.finish(f"未查询到{qq}所绑定的配置", reply_message=True, at_sender=False )
	



@maa.handle()
async def maa_handle(match: Annotated[dict[str, Any], RegexDict()],):
	if match['index']:
		index = []
		if ',' in match['index']:
			index = match['index'].split(',')
		else:
			index = match['index'].split(' ')
		await send_scheduled_tasks(index=index)
	else:
		await send_scheduled_tasks()
		
@maa_update.handle()
async def maa_update_handle():
	await send_scheduled_tasks('update')
@maa_screenshot.handle()
async def maa_screenshot_handle(event):
	await send_scheduled_tasks('screenshot')
@maa_stop.handle()
async def maa_stop_handle():
	await send_scheduled_tasks('stop')
@maa_stop_config.handle()
async def maa_stop_config_handle():
	await send_scheduled_tasks('stop_config')
@maa_schedule_ctrl.handle()
async def maa_schedule_ctrl_handle( match: Annotated[dict[str, Any], RegexDict()],):
	if match['bool'] in ['打开','开启','启动']:
		config.set_config("maa_schedule_enable",True)
		await maa_schedule_ctrl.finish("MAA定时任务已打开", reply_message=True, at_sender=False )
	else:
		config.set_config("maa_schedule_enable",False)
		await maa_schedule_ctrl.finish("MAA定时任务已关闭", reply_message=True, at_sender=False )
@maa_recall_ctrl.handle()
async def maa_recall_ctrl_handle( match: Annotated[dict[str, Any], RegexDict()],):
	if match['bool'] in ['打开','开启','启动']:
		config.set_config("maa_recall_enable",True)
		await maa_recall_ctrl.finish("MAA回调通知已打开", reply_message=True, at_sender=False )
	else:
		config.set_config("maa_recall_enable",False)
		await maa_recall_ctrl.finish("MAA回调通知已关闭", reply_message=True, at_sender=False )
@maa_schedule_delay.handle()
async def maa_schedule_delay_handle( match: Annotated[dict[str, Any], RegexDict()],):
	config.set_config("maa_task_wait",int(match['wait']))
	await maa_schedule_delay.finish(f"已暂停执行未来{(match['wait'])}次MAA定时任务", reply_message=True, at_sender=False )

@maa_config.handle()
async def maa_config_handle(event, state: T_State):
	try:
		text = '请选择要修改的配置序号：'
		state['config'] = config.get_tasks()
		count = 0
		for one_task_config in state['config']:
			text += f'\n[{count}] {one_task_config["name"]}'
			count += 1
		# text += f'\n[{count}] 新建一个配置'
		state['superuser'] = False
		state['qq'] = str(event.get_user_id())
		if event.get_user_id() in  get_driver().config.superusers:
			state['superuser'] = True
		else:
			text += f'\n\n提示：非超级管理员仅能选择自身账号绑定的配置序号'
		await maa_config.pause(text, reply_message=True, at_sender=False )
	except MatcherException:
		raise
	except Exception as e:
		logger.error(traceback.format_exc())
		await maa_config.finish(f"该功能异常，请联系工程师排查（{str(type(e).__name__)} {str(e)}）", reply_message=True, at_sender=False)

@maa_config.handle()
async def select_task_config(state: T_State,msg:Annotated[Message, EventMessage()]):
	try:
		if msg.include("text"):
			text = msg.extract_plain_text()
			if text in ['取消','退出']:
				await maa_config.finish('已退出会话', reply_message=True, at_sender=False )
			选中的配置序号 = int(text)
			if 选中的配置序号 >= len(state['config']):
				await maa_config.finish('新建配置尚未实现，已退出会话', reply_message=True, at_sender=False )
			elif 选中的配置序号 < len(state['config']):
				state['选中的配置序号'] = 选中的配置序号
				if not state['superuser'] and state['config'][state['选中的配置序号']]['qq'] != state['qq']:
					await maa_config.reject('您不能选择他人的配置，请重新输入或发送【退出】', reply_message=True, at_sender=False )
				text = f"已选择配置 【{state['config'][state['选中的配置序号']]['name']}】\n"
				text += f"请选择该配置下的配置项的序号："
				count = 0
				for key in state['config'][state['选中的配置序号']].keys():
					text += f"\n[{count}] {key}"
					count += 1
				await maa_config.pause(text, reply_message=True, at_sender=False )
			else:
				await maa_config.reject('输入有误，请重新输入或发送【退出】', reply_message=True, at_sender=False )
		else:
			await maa_config.reject('输入有误，请重新输入或发送【退出】', reply_message=True, at_sender=False )
	except MatcherException:
		raise
	except Exception as e:
		logger.error(traceback.format_exc())
		await maa_config.finish(f"该功能异常，请联系工程师排查（{str(type(e).__name__)} {str(e)}）", reply_message=True, at_sender=False)

@maa_config.handle()
async def fix_task_config(state: T_State,msg:Annotated[Message, EventMessage()]):
	try:
		if msg.include("text"):
			text = msg.extract_plain_text()
			if text in ['取消','退出']:
				await maa_config.finish('已退出会话', reply_message=True, at_sender=False )
			单条配置下的配置项序号 = int(text)
			if 单条配置下的配置项序号 < len(list(state['config'][state['选中的配置序号']].keys())):
				state['选中的单条配置下的配置项名称'] = list(state['config'][state['选中的配置序号']].keys())[单条配置下的配置项序号]
				if not state['superuser'] and state['选中的单条配置下的配置项名称'] == 'qq':
					await maa_config.reject('您没有修改该配置项的权限，请重新输入或发送【退出】', reply_message=True, at_sender=False )
				if state['选中的单条配置下的配置项名称'] != 'tasks':
					text = f"请输入【{state['选中的单条配置下的配置项名称']}】修改后的值：（当前值：{state['config'][state['选中的配置序号']][state['选中的单条配置下的配置项名称']]}）"
					await maa_config.pause(text, reply_message=True, at_sender=False )
				else:
					text = '请选择任务序号：\n（回复【1】表示修改一个任务，【1+】表示在任务1之前新增一个任务，【1-】表示删除第一个任务，【+】表示在最后新增一个任务）\n'
					count = 0
					for task in state['config'][state['选中的配置序号']][state['选中的单条配置下的配置项名称']]:
						task_name = task['type']
						if 'id' in task:
							task_name += "_" + task['id']
						text += f'\n[{count}] {task_name}'
						count += 1
					await maa_config.pause(text, reply_message=True, at_sender=False )
			else:
				await maa_config.reject('输入有误，请重新输入或发送【退出】', reply_message=True, at_sender=False )
		else:
			await maa_config.reject('输入有误，请重新输入或发送【退出】', reply_message=True, at_sender=False )
	except MatcherException:
		raise
	except Exception as e:
		logger.error(traceback.format_exc())
		await maa_config.finish(f"该功能异常，请联系工程师排查（{str(type(e).__name__)} {str(e)}）", reply_message=True, at_sender=False)

@maa_config.handle()
async def set_task_config(state: T_State,msg:Annotated[Message, EventMessage()]):
	try:
		if msg.include("text"):
			text = msg.extract_plain_text()
			if text in ['取消','退出']:
				await maa_config.finish('已退出会话', reply_message=True, at_sender=False )
			if state['选中的单条配置下的配置项名称'] == 'name':
				state['config'][state['选中的配置序号']][state['选中的单条配置下的配置项名称']] = text
				config.set_tasks(state['config'])
				await maa_config.finish(f'已修改配置名为：{text}', reply_message=True, at_sender=False )
			elif state['选中的单条配置下的配置项名称'] == 'priority':
				state['config'][state['选中的配置序号']][state['选中的单条配置下的配置项名称']] = int(text)
				config.set_tasks(state['config'])
				await maa_config.finish(f'已修改配置优先级为：{text}', reply_message=True, at_sender=False )
			elif state['选中的单条配置下的配置项名称'] == 'tasks':
				if '+' == text:
					state['op'] = 'append'
					maa_config.send('请编辑任务后提交：', reply_message=True, at_sender=False )
				elif '+' in text:
					state['op'] = 'insert'
					state['选中的单个配置下的任务序号'] = int(text.replace('+',''))
					maa_config.send('请编辑任务后提交：', reply_message=True, at_sender=False )
					task_content_json = json.dumps(config.get_template_task(), ensure_ascii=False, indent=4, separators=(', ', ': '))
					await maa_config.pause(task_content_json)
				elif '-' in text:
					state['op'] = 'del'
					state['选中的单个配置下的任务序号'] = int(text.replace('-',''))
					maa_config.send('【确认】删除该任务？回复【确认】或【取消】', reply_message=True, at_sender=False )
					task_content = state['config'][state['选中的配置序号']][state['选中的单条配置下的配置项名称']][state['选中的单个配置下的任务序号']]
					task_content_json = json.dumps(task_content, ensure_ascii=False, indent=4, separators=(', ', ': '))
					await maa_config.pause(task_content_json)

				else:
					state['op'] = 'fix'
					state['选中的单个配置下的任务序号'] = int(text)
					maa_config.send('请对该任务进行修改后提交：（需要回复修改后的整个json文本）', reply_message=True, at_sender=False )
					task_content = state['config'][state['选中的配置序号']][state['选中的单条配置下的配置项名称']][state['选中的单个配置下的任务序号']]
					task_content_json = json.dumps(task_content, ensure_ascii=False, indent=4, separators=(', ', ': '))
					await maa_config.pause(task_content_json)
					
			else:
				await maa_config.reject('输入有误，请重新输入或发送【退出】', reply_message=True, at_sender=False )
	except MatcherException:
		raise
	except Exception as e:
		logger.error(traceback.format_exc())
		await maa_config.finish(f"该功能异常，请联系工程师排查（{str(type(e).__name__)} {str(e)}）", reply_message=True, at_sender=False)

@maa_config.handle()
async def set_task_config_confirm(state: T_State,msg:Annotated[Message, EventMessage()]):
	try:
		if msg.include("text"):
			text = msg.extract_plain_text()
			if text in ['取消','退出']:
				await maa_config.finish('已退出会话', reply_message=True, at_sender=False )

			if state['op'] == 'fix':
				try:
					task_json = json.loads(text)
				except Exception as e:
					await maa_config.reject(f"输入有误，请重新输入或发送【退出】：{str(type(e).__name__)} "+str(e), reply_message=True, at_sender=False )
				state['config'][state['选中的配置序号']][state['选中的单条配置下的配置项名称']][state['选中的单个配置下的任务序号']] = task_json
				config.set_tasks(state['config'])
				await maa_config.finish(f"配置已修改", reply_message=True, at_sender=False )
			elif state['op'] == 'del':
				if text in ['是','确认','确定']:
					del state['config'][state['选中的配置序号']][state['选中的单条配置下的配置项名称']][state['选中的单个配置下的任务序号']]
					config.set_tasks(state['config'])
					await maa_config.finish(f"配置已修改", reply_message=True, at_sender=False )
			elif state['op'] == 'append':
				try:
					task_json = json.loads(text)
				except Exception as e:
					await maa_config.reject(f"输入有误，请重新输入或发送【退出】：{str(type(e).__name__)} "+str(e), reply_message=True, at_sender=False )
				state['config'][state['选中的配置序号']][state['选中的单条配置下的配置项名称']].append(task_json)
				config.set_tasks(state['config'])
				await maa_config.finish(f"配置已修改", reply_message=True, at_sender=False )
			elif state['op'] == 'insert':
				try:
					task_json = json.loads(text)
				except Exception as e:
					await maa_config.reject(f"输入有误，请重新输入或发送【退出】：{str(type(e).__name__)} "+str(e), reply_message=True, at_sender=False )
				state['config'][state['选中的配置序号']][state['选中的单条配置下的配置项名称']].insert(state['选中的单个配置下的任务序号'], task_json)
				config.set_tasks(state['config'])
				await maa_config.finish(f"配置已修改", reply_message=True, at_sender=False )
		else:
			await maa_config.reject('输入有误，请重新输入或发送【退出】', reply_message=True, at_sender=False )
	except MatcherException:
		raise
	except Exception as e:
		logger.error(traceback.format_exc())
		await maa_config.finish(f"该功能异常，请联系工程师排查（{str(type(e).__name__)} {str(e)}）", reply_message=True, at_sender=False)






require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler
@scheduler.scheduled_job("cron", hour="4,12,20", misfire_grace_time=60)
async def run_maa():
	bot: Bot = get_bot()
	if config.get_config("maa_schedule_enable"):
		wait = config.get_config("maa_task_wait")
		if wait > 0:
			config.set_config("maa_task_wait", wait-1)
			await bot.send_group_msg( group_id=config.get_config("notice_group_id"), message="跳过本次MAA定时任务")
		else:
			await bot.send_group_msg( group_id=config.get_config("notice_group_id"), message="下发MAA定时任务")
			await send_scheduled_tasks(schedule=True)
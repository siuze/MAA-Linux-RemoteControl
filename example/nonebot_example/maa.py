import asyncio
import base64
from typing import Any

from nonebot import Bot, get_bot, logger

# 适配器导入示例（以 OneBot V11 为例，如使用其它平台适配器请自行替换）
try:
	from nonebot.adapters.onebot.v11 import Message, MessageSegment
except ImportError:
	# 若无 OneBot V11 环境时的通用兜底定义
	class MessageSegment:  # type: ignore
		@staticmethod
		def text(s: str) -> dict[str, Any]:
			return {"type": "text", "data": {"text": s}}

		@staticmethod
		def image(img: bytes) -> dict[str, Any]:
			return {"type": "image", "data": {"file": img}}

		@staticmethod
		def at(user_id: Any) -> dict[str, Any]:
			return {"type": "at", "data": {"qq": str(user_id)}}

	class Message(list):  # type: ignore
		pass

from .typeddef import Notice


async def send_notice(msg_chain: Any, group_id: int = 1234567) -> None:
	"""向指定群聊推送通知消息"""
	logger.info("准备向群聊 %s 发送通知消息", group_id)
	try:
		bot: Bot = get_bot()
		await bot.send_group_msg(group_id=group_id, message=Message(msg_chain))
	except Exception as e:
		logger.error("发送群消息失败: %s", e)


async def handle_receive(msg: Notice) -> dict[str, str]:
	"""处理来自 MAA-LRC 客户端的 Notice 回调通知"""
	try:
		msg_type = msg.get("type")
		status = msg.get("status")
		payload = msg.get("payload", "")

		# 1. 即时回执、重要通知、配置启动通知
		if msg_type in ("receipt", "important_notice", "config_start"):
			if payload:
				await send_notice([MessageSegment.text(payload)])

		# 2. 内核更新日志分片推送
		elif msg_type == "update_log" and status != "OK":
			update_log = payload
			part_index = 0
			while part_index < len(update_log):
				await send_notice([MessageSegment.text(update_log[part_index : part_index + 500])])
				part_index += 500
				await asyncio.sleep(2)

		# 3. 配置执行结束通知
		elif msg_type == "config_end" and "config" in msg:
			cfg = msg["config"]
			msg_chain = [MessageSegment.text(f"配置 【{cfg.get('id', '未知')}】执行结束\n")]
			if "qq" in cfg:
				msg_chain.append(MessageSegment.at(cfg["qq"]))
			await send_notice(msg_chain)

		# 4. 单项任务执行结果通知
		elif msg_type == "task_result" and "config" in msg:
			cfg = msg["config"]
			tasks = cfg.get("tasks", [])
			config_task = tasks[0] if tasks else {"name": "未知任务"}
			text = f"【配置 {cfg.get('id', '未知')} 】\n【任务 {config_task.get('name', '未知')} 】"

			if "duration" in msg:
				text += f"\n耗时 {int(msg['duration'])}s"

			if status in ("SUCCESS", "OK"):
				text += "\n任务正常执行"
			elif status == "FAILED":
				text += "\n任务执行失败或异常"

			if payload:
				text += f"\n{payload[:1000]}"

			logger.info(text)
			msg_chain = [MessageSegment.text(text)]

			# 附加任务截图（如果有）
			if "image" in msg and msg["image"]:
				img_bytes = base64.b64decode(msg["image"])
				msg_chain.append(MessageSegment.image(img_bytes))

			if "qq" in cfg:
				msg_chain.append(MessageSegment.at(cfg["qq"]))

			await send_notice(msg_chain)

		return {"status": "success"}

	except Exception as e:
		logger.exception("处理 MAA 回调通知发生异常: %s", e)
		return {"status": "error", "msg": f"{type(e).__name__}: {e}"}

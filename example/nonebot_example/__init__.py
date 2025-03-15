
from nonebot import require

from .ws import send_scheduled_tasks

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler  # noqa: E402

@scheduler.scheduled_job("cron", hour="4,12,20", misfire_grace_time=60)
async def run_maa():
	await send_scheduled_tasks()


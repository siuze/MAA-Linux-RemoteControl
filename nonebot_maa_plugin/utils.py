# 一些格式转换什么的
from io import BytesIO

from PIL import Image


def png2jpg(img, quality: int = 75):
	"""
	压缩一下png图片，转成jpg减少体积
	:param:
		img: Bytes[] 图片的二进制数据rb
		quality: int=75 压缩后的图像质量，0~100
	:return: str 时间长度的自然语言
	"""
	img = Image.open(BytesIO(img)).convert("RGB")
	bytesIO = BytesIO()
	img.save(bytesIO, format="JPEG", quality=quality)  # 图像质量默认为75
	return bytesIO.getvalue()


def text_transform(payload):
	# 用一些抽象话来规避腾讯的防诈骗提醒
	return payload.replace("币", "幤").replace("信", "伩").replace("免费单抽机会", "🆓单🤡🐔会").replace("奖励", "🥇💪").replace("领取", "0⃣取").replace("抽签", "🤡签").replace("重要", "🀄💊")


def seconds_format(time_cost: int):
	"""
	耗费时间自然语言转换
	:param: time_cost:
	:return: str 时间长度的自然语言
	"""
	min = 60
	hour = 60 * 60
	day = 60 * 60 * 24
	if not time_cost or time_cost < 0:
		return ""
	elif time_cost < min:
		return f"{int(time_cost)}秒"
	elif time_cost < hour:
		return f"{int(time_cost/min)}分{int(time_cost%min)}秒"
	elif time_cost < day:
		cost_hour, cost_min = divmod(time_cost, hour)
		return f"{int(time_cost/hour)}小时{seconds_format(cost_min)}"
	else:
		cost_day, cost_hour = divmod(time_cost, day)
		return f"{int(cost_day)}天{seconds_format(cost_hour)}"

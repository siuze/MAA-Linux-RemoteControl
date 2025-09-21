from pathlib import Path

import cv2
from loguru import logger as lg

def 检查免费单抽(img_path: str):
	lg.info(f"{img_path=}")
	img = cv2.imread(img_path)
	img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
	template = cv2.imread(str(Path(__file__).parent.parent / "data/template/free_gacha.png"), 0)
	# print(img.shape)
	res = cv2.matchTemplate(img[525:900, 1500:1920], template, cv2.TM_CCOEFF_NORMED)
	min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
	return max_val


def 检查活动红点(img_path: str):
	img = cv2.imread(img_path)
	imageNeedleR, imageNeedleG, imgB = cv2.split(img)
	# img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
	template = cv2.imread(str(Path(__file__).parent.parent / "data/template/twinkle_square.png"))
	imageNeedleR, imageNeedleG, templateB = cv2.split(template)
	res = cv2.matchTemplate(imgB[105:375, 0:300], templateB, cv2.TM_CCOEFF_NORMED)
	min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
	return max_val


def 检查基建异常(img_path:str):
	img = cv2.imread(img_path)
	img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
	max_val_max = 0
	for img_name in ('日间','大荒','迷宫','彩六','银凇','视相','梦乡白天'):
		template = cv2.imread(str(Path(__file__).parent.parent / f"data/template/{img_name}-基建感叹号.png"), 0)
		res = cv2.matchTemplate(img[840:1020, 1485:1695], template, cv2.TM_CCOEFF_NORMED)
		min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
		lg.info(f"{img_name}-基建感叹号 模板匹配得分 {max_val}")
		max_val_max = max(max_val_max, max_val)
	return max_val_max


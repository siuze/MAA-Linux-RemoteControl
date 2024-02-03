from pathlib import Path
import cv2
def match_free_gacha(img_path='1.png'):
	img = cv2.imread(img_path)
	img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
	template = cv2.imread(str(Path(__file__).parent / f"template/free_gacha.png"), 0)
	# print(img.shape)
	res = cv2.matchTemplate(img[350:600, 1000:1280] , template, cv2.TM_CCOEFF_NORMED)
	min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
	return max_val
def match_activity(img_path='1.png'):
	img = cv2.imread(img_path)
	img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
	template = cv2.imread(str(Path(__file__).parent / f"template/twinkle_square.png"), 0)
	res = cv2.matchTemplate(img[70:250, 0:200] , template, cv2.TM_CCOEFF_NORMED)
	min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
	return max_val
def match_infrast_oops(img_path='1.png'):
	img = cv2.imread(img_path)
	img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
	template = cv2.imread(str(Path(__file__).parent / f"template/infrast_oops.png"), 0)
	res = cv2.matchTemplate(img[560:680, 990:1130] , template, cv2.TM_CCOEFF_NORMED)
	min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
	return max_val
# print(match_free_gacha('/volume1/程序/maa/Python/img/after_任务完成后主界面.png'))
# print(match_activity('2.png'))
# print(match_activity('3.jpg'))
# print(match_activity('/volume1/程序/maa/Python/img/after_任务完成后主界面.png'))
print(match_infrast_oops('/volume1/程序/maa/Python/img/after_任务完成后主界面.png'))
# print(match_infrast_oops('2.png'))
# print(match_infrast_oops('3.jpg'))
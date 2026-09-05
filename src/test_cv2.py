import cv2
from src.check_oops import 检查活动红点

img_path = "/home/ubuntu/siuze/prj/maa/python/data/img/after_任务完成后主界面.png"
img = cv2.imread(img_path)
if img is not None:
	imageNeedleR, imageNeedleG, imgB = cv2.split(img)
	crop = imgB[105:375, 0:300]
	cv2.imwrite("crop.jpg", crop)
	print("Saved!")
	print(检查活动红点(img_path))

import cv2

# # 读取图片
img = '/home/ubuntu/siuze/prj/maa/python/data/img/after_任务完成后主界面.png'
img = cv2.imread(img)
imageNeedleR, imageNeedleG, imgB = cv2.split(img)
crop = imgB[105:375, 0:300]
cv2.imwrite('crop.jpg', crop)
print('Saved!')

from check_oops import *
print(检查活动红点('/home/ubuntu/siuze/prj/maa/python/data/img/after_任务完成后主界面.png'))
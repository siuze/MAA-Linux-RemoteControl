import requests
import base64
import json
from loguru import logger as lg
from pathlib import Path
import yaml


with open(str(Path(__file__).parent / "../config/asst.yaml"), 'r', encoding='utf8') as config_f:
	asst_config = yaml.safe_load(config_f)
to_id = str(asst_config['msg']['to'])
url = asst_config['msg']['url']

def send_msg(msg:str, img=None, flag:int=0):
	"""
	自用的API接口 POST请求，发送json内容，
	{
		"id": 对方的QQ号或者群号,
		"msg": 消息文本,
		"type": 'group', 账号类型 group | private
		"flag": 0, 附带的一些保留标志位，这里没用上
		"img": 图片的base64字符串，没有图片就不包含这个img字段
	}
	
	"""
	while msg[-1:] == '\n':
		msg = msg[:-1]
	
	data={
		"id": to_id,
		"msg": msg,
		"type": 'group',
		"flag": flag,
	}
	if img :
		data['img'] = base64.b64encode(img).decode("utf-8")


	lg.info("准备发送消息")
	lg.info(msg)

	resp = requests.post(url, json.dumps(data))
	lg.info('发送post数据请求成功!')
	lg.info('返回post结果如下：')
	lg.info(resp.text)


def send_qqimagedeliver(msg:str, img=None):
	"""
	https://github.com/tkkcc/qqimagedeliver 的API规范，但是还没测试，因为我已经不用了
	"""
	while msg[-1:] == '\n':
		msg = msg[:-1]
	lg.info("准备发送消息")
	lg.info(msg)
	data={
		"image": None, # base64编码图片
		"to": to_id, # 接收QQ号或群号
		"info": msg, # 文字信息
		} 
	if img :
		data['image'] = base64.b64encode(img).decode("utf-8")
	url=url
	html = requests.post(url, data=data)
	lg.info('发送post数据请求成功!')
	lg.info('返回post结果如下：')
	lg.info(html.text)

def JustPrint(msg:str, img=None, flag:int=0):
	print(msg)
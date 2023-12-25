from loguru import logger as lg
import json
from _global import global_var
from pathlib import Path
import yaml
import websocket
import traceback
import time

def on_open(wsapp):
    lg.info("MAA成功连接到WS服务端")
def on_message(wsapp, msg):
	lg.info("收到WS消息:")
	lg.info(msg)
	try:
		data = json.loads(msg)
	except ValueError:
		global_var.get("send_msg_waiting_queue").put({'type':'receipt','payload':'收到的消息无法通过json格式化'})
	global_var.get("tasks_config_waiting_queue").put({"data":data,})
	recall = {
			"status": "SUCCESS",
			"payload": "MAA已收到一条任务配置，加入任务处理队列等待运行",
			"type": "receipt",
		}
	global_var.get("send_msg_waiting_queue").put(recall)
def on_error(wsapp, e):
	lg.error(f"WS连接出错 {e}")
def on_close(wsapp, close_status_code, close_reason):
	lg.info(f"WS连接关闭 {close_status_code} {close_reason}")
def ws_client():
	with open(str(Path(__file__).parent.parent / "config/asst.yaml"), 'r', encoding='utf8') as config_f:
		ws_url = yaml.safe_load(config_f)['python']['ws']
	while True:
		try:
			wsapp = websocket.WebSocketApp(ws_url,
									on_open=on_open,
									on_message=on_message,
									on_error=on_error,
									on_close=on_close)
			global_var.set("wsapp",wsapp)
			global_var.get("wsapp").run_forever()
		except Exception as e:
			lg.error(traceback.format_exc())
		finally:
			time.sleep(5)

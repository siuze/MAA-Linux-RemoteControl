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
	config_type = "一般"
	if "type" in data and data['type'] == "interrupt":
		config_type = "中断"
		global_var.get("interrupt_tasks_waiting_queue").put({"data":data,})
	else:
		global_var.get("tasks_config_waiting_queue").put({"data":data,})
	recall = {
			"status": "SUCCESS",
			"payload": f"MAA已收到一条{config_type}任务配置：【{data['name']}】，加入队列等待运行",
			"type": "receipt",
		}
	global_var.get("send_msg_waiting_queue").put(recall)
def on_error(wsapp, e):
	lg.error(f"WS连接出错 {e}")
def on_close(wsapp, close_status_code, close_reason):
	lg.info(f"WS连接关闭 {close_status_code} {close_reason}")
	if global_var.get('exit_all'):
		lg.info(f"检测到exit_all标志")
		exit()
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
			global_var.get("wsapp").run_forever(ping_interval=10,ping_timeout=3)
		except KeyboardInterrupt:
			lg.error('检测到KeyboardInterrupt，准备5s后退出WS线程')
			time.sleep(5)
			try:
				wsapp.close()
			except:
				pass
			exit()
		except Exception as e:
			lg.error(traceback.format_exc())
		finally:
			time.sleep(5)

import faulthandler
faulthandler.enable()
from pathlib import Path
import json
import time
import traceback
from loguru import logger as lg
import gc
from threading import Thread
import os
lg.add(str(Path(__file__).parent / f"logs/log_{time.strftime('%Y-%m-%d', time.localtime()) }.log"), rotation="1 day",retention='30 days')

from cache import read_cache, save_cache
from maa import MAA
from ws import ws_client


from _global import global_var

def handle_interrupt_tasks_waiting_queue():
	lg.info("启用中断任务配置队列轮询处理")
	while True:
		if global_var.get('exit_all'):
			exit()
		try:
			time.sleep(2)
			if not global_var.get("interrupt_tasks_waiting_queue").empty():
				if  global_var.get("my_maa") == None:
					lg.info("激活MAA")
					global_var.set("my_maa", MAA())
					global_var.get("my_maa").connect(init=True)
				lg.info("还有尚未完成的中断任务配置，将队列中的第一个提交到处理函数中")
				global_var.get("my_maa").interrupt_tasks_handler(data=global_var.get("interrupt_tasks_waiting_queue").queue[0]['data'])
				lg.info("该中断任务配置处理完成，将其清理出队列")
				global_var.set("accomplish_config_num",  global_var.get("accomplish_config_num") + 1)
				global_var.get("interrupt_tasks_waiting_queue").get()
				save_cache()
				lg.info(f"中断任务配置队列中剩余{global_var.get('interrupt_tasks_waiting_queue').qsize()}个任务配置")
		except KeyboardInterrupt:
			lg.error('检测到KeyboardInterrupt，退出WS待发送消息队列线程')
			exit()
		except Exception as e:
			lg.error(traceback.format_exc())
def handle_tasks_config_waiting_queue():
	lg.info("启用一般任务配置队列轮询处理")
	sleep_state =True
	while True:
		if global_var.get('exit_all'):
			exit()
		try:
			time.sleep(5)
			if not global_var.get("tasks_config_waiting_queue").empty():
				if sleep_state or global_var.get("my_maa") == None:
					lg.info("激活MAA")
					global_var.set("my_maa", MAA())
					global_var.get("my_maa").connect(init=True)
					sleep_state =False
				lg.info("还有尚未完成的一般任务配置，将队列中的第一个提交到处理函数中")
				global_var.get("my_maa").tasks_handler(data=global_var.get("tasks_config_waiting_queue").queue[0]['data'])
				lg.info("该一般任务配置处理完成，将其清理出队列")
				global_var.set("accomplish_config_num",  global_var.get("accomplish_config_num") + 1)
				global_var.get("tasks_config_waiting_queue").get()
				if global_var.get("clean_all_config_tag") == True:
					lg.info("收到指令，清空所有配置")
					with global_var.get("tasks_config_waiting_queue").mutex:
						global_var.get("tasks_config_waiting_queue").queue.clear()
					global_var.set("clean_all_config_tag", False)
				save_cache()
				lg.info(f"一般任务配置队列中剩余{global_var.get('tasks_config_waiting_queue').qsize()}个任务配置")
			else:
				if not sleep_state and global_var.get("interrupt_tasks_waiting_queue").empty():
					lg.info(f"任务配置队列已全部处理完（含中断任务）")
					lg.info(f"清理内存，删除MAA实例，进入休眠模式")
					global_var._del("my_maa")
					sleep_state = True
					global_var.set("my_maa", None)

					if global_var.get("accomplish_config_num") > 0:
						time.sleep(5)
						if global_var.get("tasks_config_waiting_queue").empty() and global_var.get("interrupt_tasks_waiting_queue").empty():
							lg.info(f"暂时通过退出进程以规避内存泄露问题")
							# save_cache()
							global_var.exit_all()
							exit()
		except KeyboardInterrupt:
			lg.error('检测到KeyboardInterrupt，退出一般任务配置队列轮询线程')
			exit()

		except Exception as e:
			lg.error(traceback.format_exc())

def handle_send_msg_waiting_queue():
	lg.info("启用消息队列轮询发送")
	while True:
		if global_var.get('exit_all'):
			try:
				global_var.get("wsapp").close()
			except Exception as e:
				lg.error(str(e))
			exit()
		try:
			if not global_var.get("send_msg_waiting_queue").empty():
				global_var.get("wsapp").send(json.dumps(global_var.get("send_msg_waiting_queue").queue[0], ensure_ascii=False))
				global_var.get("send_msg_waiting_queue").get()
				save_cache()
		except KeyboardInterrupt:
			lg.error('检测到KeyboardInterrupt，退出WS待发送消息队列线程')
			exit()
		except Exception as e:
			lg.error(traceback.format_exc())
		finally:
			time.sleep(1) #需要sleep一下减少CPU占用



read_cache()
# 创建 Thread 实例
WS客户端线程 = Thread(target=ws_client, args=())
WS待发送消息队列 = Thread(target=handle_send_msg_waiting_queue, args=())

MAA任务配置处理队列 = Thread(target=handle_tasks_config_waiting_queue, args=())
MAA中断任务配置处理队列 = Thread(target=handle_interrupt_tasks_waiting_queue, args=())

# 启动线程运行
WS客户端线程.start()
WS待发送消息队列.start()
MAA任务配置处理队列.start()
MAA中断任务配置处理队列.start()


WS客户端线程.join()
WS待发送消息队列.join()
MAA任务配置处理队列.join()
MAA中断任务配置处理队列.join()
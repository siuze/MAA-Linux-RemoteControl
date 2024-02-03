from queue import Queue
import gc

from loguru import logger as lg
class GlobalVar:
	def __init__(self):
		self._global = dict(
		my_maa = None,
		wsapp = None,
		clean_all_config_tag = False,
		exit_all = False,
		accomplish_config_num = 0,
		tasks_config_waiting_queue = Queue(),
		interrupt_tasks_waiting_queue = Queue(),
		send_msg_waiting_queue = Queue()
		)

 
	def set(self,key, value):
		self._global[key] = value
	
	def get(self, key, defValue=None):
		try:
			return self._global[key]
		except KeyError:
			return defValue
	def _del(self, key):
		del self._global[key]
		gc.collect()

	def exit_all(self):
		self.set('exit_all',True)


global_var = GlobalVar()
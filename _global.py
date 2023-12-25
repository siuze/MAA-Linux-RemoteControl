from queue import Queue
import gc


class GlobalVar:
	def __init__(self):
		self._global = dict(
		my_maa = None,
		wsapp = None,
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
global_var = GlobalVar()
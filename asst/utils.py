from typing import Union, Dict, List, Any, Type
from enum import Enum, IntEnum, unique, auto

JSON = Union[Dict[str, Any], List[Any], int, str, float, bool, Type[None]]


class InstanceOptionType(IntEnum):
	touch_type = 2
	deployment_with_pause = 3


@unique
class Message(Enum):
	"""
	回调消息

	请参考 docs/回调消息.md
	"""

	# /* Global Info */
	InternalError = 0  # 内部错误
	InitFailed = 1  # 初始化失败
	ConnectionInfo = 2  # 连接相关信息
	AllTasksCompleted = 3  # 全部任务完成
	AsyncCallInfo = 4  # 外部异步调用信息

	# /* TaskChain Info */
	TaskChainError = 10000  # 任务链执行/识别错误
	TaskChainStart = 10001  # 任务链开始
	TaskChainCompleted = 10002  # 任务链完成
	TaskChainExtraInfo = 10003  # 任务链额外信息
	TaskChainStopped = 10004  # 任务链手动停止

	# /* SubTask Info */
	SubTaskError = 20000  # 原子任务执行/识别错误
	SubTaskStart = 20001  # 原子任务开始
	SubTaskCompleted = 20002  # 原子任务完成
	SubTaskExtraInfo = 20003  # 原子任务额外信息
	SubTaskStopped = 20004  # 原子任务手动停止


@unique
class Version(Enum):
	"""
	目标版本
	"""

	Nightly = auto()

	Beta = auto()

	Stable = auto()

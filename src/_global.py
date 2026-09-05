from enum import Enum, IntEnum
from typing import Any, Literal, NotRequired, TypedDict


class ErrorCode(IntEnum):
	"""MAA-LRC 标准语义化错误代码体系"""
	SUCCESS = 0
	NONE = 1

	# 网关与协议解析错误 (1000 - 1999)
	ERR_JSON_PARSE = 1001
	ERR_SCHEMA_VALIDATION = 1002
	ERR_INVALID_TASK_TYPE = 1003

	# 设备与通信层错误 (2000 - 2999)
	ERR_ADB_PORT_SCAN_FAILED = 2001
	ERR_ADB_CONNECT_FAILED = 2002
	ERR_ADB_SCREENCAP_FAILED = 2003
	ERR_ADB_DEVICE_OFFLINE = 2004

	# MAA 内核与执行错误 (3000 - 3999)
	ERR_MAA_CRASH = 3001
	ERR_STAGE_NAVIGATION = 3002
	ERR_FIGHT_START_FAILED = 3003
	ERR_STAGE_NOT_OPEN = 3004
	ERR_TASK_CHAIN_ERROR = 3005
	ERR_SUBTASK_ERROR = 3006
	ERR_SANITY_DEPLETED = 3007

	# 外部控制与调度事件 (4000 - 4999)
	ERR_TASK_ABORTED = 4001
	ERR_CONFIG_SKIPPED = 4002
	ERR_COMMAND_TIMEOUT = 5001


class NoticeType(str, Enum):
	TASK_RESULT = "task_result"
	CONFIG_START = "config_start"
	CONFIG_END = "config_end"
	UPDATE_LOG = "update_log"
	RECEIPT = "receipt"
	IMPORTANT_NOTICE = "important_notice"


class NoticeStatus(str, Enum):
	SUCCESS = "SUCCESS"
	FAILED = "FAILED"
	NONE = "NONE"
	OK = "OK"


class WeekdayCondition(TypedDict):
	weekday: list[Literal[1, 2, 3, 4, 5, 6, 7]]


HourCompare = TypedDict(
	"HourCompare",
	{
		"<": NotRequired[Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]],
		">": NotRequired[Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]],
	},
)


class HourCondition(TypedDict):
	hour: HourCompare


class LogicCondition(TypedDict):
	executed: NotRequired[str]
	enable: NotRequired[str]


TaskCondition = TypedDict(
	"TaskCondition",
	{
		"weekday": NotRequired[list[Literal[1, 2, 3, 4, 5, 6, 7]]],
		"hour": NotRequired[HourCompare],
		"not": NotRequired[LogicCondition],
		"and": NotRequired[list[LogicCondition]],
		"or": NotRequired[list[LogicCondition]],
	},
)


TaskTypeLiteral = Literal[
	"StartUp",
	"CloseDown",
	"Fight",
	"Recruit",
	"Infrast",
	"Mall",
	"Award",
	"Custom",
	"Roguelike",
	"Copilot",
	"SSSCopilot",
	"Depot",
	"OperBox",
	"ReclamationAlgorithm",
	"SingleStep",
	"VideoRecognition",
	"Update",
	"Screenshot",
	"Stop_config",
	"Stop",
]


class Task(TypedDict):
	type: TaskTypeLiteral
	name: str
	enable: NotRequired[bool]
	screenshot: NotRequired[Literal["before", "after", "both"]]
	block: NotRequired[Literal["executed", "enable"]]
	params: NotRequired[dict[str, Any]]
	condition: NotRequired[TaskCondition]


class TaskConfig(TypedDict):
	id: str
	type: Literal["normal", "interrupt"]
	tasks: list[Task]
	priority: NotRequired[int]  # 配置优先级，默认为 0；< 0 代表次要任务，当队列存在非负数优先级任务时会被中止让位


class Notice(TypedDict):
	type: Literal["task_result", "config_start", "config_end", "update_log", "receipt", "important_notice"]
	status: Literal["SUCCESS", "FAILED", "NONE", "OK"]
	payload: str
	config: NotRequired[TaskConfig]
	image: NotRequired[str]
	duration: NotRequired[float]
	code: NotRequired[int]  # 兼容语义化错误代码


facility_translate: dict[str, str] = {
	"Mfg": "制造站",
	"Trade": "贸易站",
	"Power": "发电站",
	"Control": "控制中枢",
	"Reception": "会客室",
	"Office": "人力办公室",
	"Dorm": "宿舍",
	"Training": "训练室",
}

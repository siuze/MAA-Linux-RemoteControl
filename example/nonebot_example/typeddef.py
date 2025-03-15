from typing import Any, Literal, NotRequired, TypedDict

class WeekdayCondition(TypedDict):
	weekday: list[Literal[1,2,3,4,5,6,7]]

HourCompare = TypedDict('HourCompare', {'<':NotRequired[Literal[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23]], '>':NotRequired[Literal[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23]]})

class HourCondition(TypedDict):
	hour: HourCompare

class LogicCondition(TypedDict):
	executed: NotRequired[str]
	enable: NotRequired[str]
	# not: LogicCondition
	# and: list[LogicCondition]
	# or: list[LogicCondition]

TaskCondition = TypedDict('TaskCondition',
	{
	'weekday': NotRequired[list[Literal[1,2,3,4,5,6,7]]],
	'hour': NotRequired[HourCompare],
	'not': NotRequired[LogicCondition],
	'and': NotRequired[list[LogicCondition]],
	'or': NotRequired[list[LogicCondition]],
	}
	)


class Task(TypedDict):
	type: Literal['StartUp','CloseDown','Fight','Recruit','Infrast','Mall', 'Award',
'Custom', 'Roguelike','Copilot','SSSCopilot','Depot','OperBox','ReclamationAlgorithm','SingleStep','VideoRecognition','Update','Screenshot','Stop_config','Stop']
	name: str
	enable: NotRequired[bool]
	screenshot: NotRequired[Literal['before', 'after']]
	block: NotRequired[Literal['executed', 'enable']]
	params: NotRequired[dict[str, Any]]
	condition: NotRequired[TaskCondition]


class TaskConfig(TypedDict):
	id: str
	type: Literal['normal', 'interrupt']
	tasks: list[Task]


class Notice(TypedDict):
	type: Literal['task_result', 'config_start', 'config_end', 'update_log', 'receipt', 'important_notice']
	status: Literal['SUCCESS','FAILED','OK']
	payload: str
	config: NotRequired[TaskConfig]
	image: NotRequired[str]
	duration: NotRequired[float]

import json
from pathlib import Path


class Config:
	def __init__(self) -> None:
		self.config_path = Path(__file__).parent / "data/maa/config.json"
		self.tasks_config_path = Path(__file__).parent / "data/maa/tasks_config.json"
		self.update_config_path = Path(__file__).parent / "data/maa/tasks_update.json"
		with open(self.config_path, "r", encoding="utf8") as f:
			self.config = json.load(f)

	def get_tasks(self, _file: str = ""):
		path = self.tasks_config_path
		if _file:
			if _file == "update":
				path = self.update_config_path
			else:
				path = Path(__file__).parent / f"data/maa/tasks_{_file}.json"
		with open(path, "r", encoding="utf8") as f:
			return json.load(f)

	def get_update_task(self):
		with open(self.update_config_path, "r", encoding="utf8") as f:
			return json.load(f)

	def get_template_task(self):
		with open(Path(__file__).parent / "data/maa/tasks_template.json", "r", encoding="utf8") as f:
			return json.load(f)

	def set_tasks(self, config):
		path = self.tasks_config_path
		with open(path, "w", encoding="utf8") as file:
			file.write(json.dumps(config, ensure_ascii=False, indent=4, separators=(", ", ": ")))

	def get_config(self, key):
		return self.config[key]

	def set_config(self, key, value):
		self.config[key] = value
		with open(self.config_path, "w", encoding="utf8") as file:
			file.write(json.dumps(self.config, ensure_ascii=False, indent=4, separators=(", ", ": ")))


config = Config()

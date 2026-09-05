import ctypes
import os
import signal
import subprocess
import time
from loguru import logger as lg


class CommandTimeoutError(Exception):
	"""外部命令执行超时异常"""
	pass


class CommandExecutionError(Exception):
	"""外部命令执行失败异常"""
	pass


def set_pdeathsig(sig: int = signal.SIGTERM) -> None:
	"""
	在 Linux 系统下设置父进程消亡信号 (PR_SET_PDEATHSIG)。
	当父进程意外退出时，内核会自动向当前子进程发送该信号，防止产生孤儿进程。
	"""
	try:
		PR_SET_PDEATHSIG = 1
		libc = ctypes.CDLL("libc.so.6")
		libc.prctl(PR_SET_PDEATHSIG, sig, 0, 0, 0)
	except Exception as e:
		lg.warning(f"设置 PR_SET_PDEATHSIG 失败: {e!r}")


def safe_kill_process_group(pgid: int, grace_period: float = 1.0) -> None:
	"""
	安全且彻底地终止一个进程组，防止孤儿和僵尸进程残留。
	先发送 SIGTERM 优雅退出，超时后再发送 SIGKILL 强制杀死。
	"""
	try:
		os.killpg(pgid, signal.SIGTERM)
	except ProcessLookupError:
		return
	except Exception as e:
		lg.warning(f"向进程组 {pgid} 发送 SIGTERM 失败: {e!r}")

	deadline = time.time() + grace_period
	while time.time() < deadline:
		try:
			# 探测进程组是否仍然存在
			os.killpg(pgid, 0)
			time.sleep(0.1)
		except ProcessLookupError:
			return
		except Exception:
			break

	try:
		lg.warning(f"进程组 {pgid} 优雅终止超时，发送 SIGKILL 强杀")
		os.killpg(pgid, signal.SIGKILL)
	except ProcessLookupError:
		pass
	except Exception as e:
		lg.warning(f"向进程组 {pgid} 发送 SIGKILL 失败: {e!r}")


def run_cmd(
	cmd: str,
	timeout: float = 30.0,
	skip_timeout: bool = False,
	shell: bool = True,
	check_retcode: bool = False,
) -> bytes:
	"""
	受控安全的子进程执行函数，解决以下三大缺陷：
	1. 消除管道缓冲区满 (64KB) 导致的死锁 (使用 communicate)
	2. 超时时彻底终止整个进程组并收集 exit status，杜绝僵尸进程
	3. 抛出异常而非暴力调用 os._exit(0)
	"""
	lg.info(f"发起执行命令：{cmd}")
	p = None
	effective_timeout = None if skip_timeout else timeout
	try:
		p = subprocess.Popen(
			cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			shell=shell,
			close_fds=True,
			preexec_fn=os.setsid,  # 启动独立进程组
		)
		stdout, stderr = p.communicate(timeout=effective_timeout)
		if check_retcode and p.returncode != 0:
			err_msg = stderr.decode("utf-8", errors="replace").strip()
			raise CommandExecutionError(f"命令执行返回非0码 [{p.returncode}]: {err_msg}")
		return stdout
	except subprocess.TimeoutExpired:
		lg.error(f"命令执行超时 (>{effective_timeout}s): {cmd}")
		if p is not None:
			try:
				pgid = os.getpgid(p.pid)
				safe_kill_process_group(pgid, grace_period=1.0)
			except Exception as e:
				lg.exception(f"清理超时进程组出错: {e!r}")
			finally:
				try:
					# 确保 wait 回收子进程内核句柄，防止变为 defunct
					p.wait(timeout=2.0)
				except Exception:
					pass
		raise CommandTimeoutError(f"命令执行超时: {cmd}")
	except Exception as e:
		if not isinstance(e, (CommandTimeoutError, CommandExecutionError)):
			lg.exception(f"命令执行发生未知异常: {e!r}")
		if p is not None and p.poll() is None:
			try:
				pgid = os.getpgid(p.pid)
				safe_kill_process_group(pgid, grace_period=0.5)
				p.wait(timeout=1.0)
			except Exception:
				pass
		raise

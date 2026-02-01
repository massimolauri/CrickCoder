import subprocess
import platform
import logging
import os
import signal
from pathlib import Path
from typing import Optional, Union, List
from agno.tools import Toolkit 
from src.core.runtime.shell_manager import ShellManager

logger = logging.getLogger(__name__)

class CrickCoderShellTools(Toolkit):
    def __init__(
        self,
        base_dir: Optional[Union[Path, str]] = None,
        timeout_seconds: int = 60,
        enable_confirmation: bool = False, 
        session_id: Optional[str] = None, # New: Session Context
        **kwargs,
    ):
        confirmation_tools = ["run_shell_command"] if enable_confirmation else []

        super().__init__(
            name="shell_tools", 
            requires_confirmation_tools=confirmation_tools, 
            **kwargs
        )
        
        self.base_dir = Path(base_dir).resolve() if base_dir else Path.cwd()
        self.timeout = timeout_seconds
        self.is_windows = platform.system() == "Windows"
        self.session_id = session_id
        
        # Tools registration
        self.register(self.run_shell_command)
        self.register(self.start_interactive_session)
        self.register(self.send_shell_input)
        self.register(self.read_shell_output)
        self.register(self.close_shell_session)

    # --- Legacy / Blocking Command ---
    def _kill_process_tree(self, pid: int):
        if self.is_windows:
            try:
                subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                logger.error(f"Failed to kill Windows process tree: {e}")
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception as e:
                logger.error(f"Failed to kill Unix process group: {e}")

    def run_shell_command(self, command: str, timeout: Optional[int] = None) -> str:
        """
        Executes a shell command. 
        - If the command finishes quickly, returns the result.
        - If the command waits for input (Interactive), returns the partial output so you can respond with 'send_shell_input'.
        
        Args:
            command (str): The command to execute.
            timeout (int): Max time to wait for completion before assuming it's a long-running/interactive process (default to self.timeout).
        """
        actual_timeout = timeout if timeout is not None else self.timeout
        logger.info(f"🐚 RUN (Smart Mode): {command} | Session: {self.session_id}")

        if not self.session_id:
            # Fallback for safe mode or no-session context (Legacy Blocking)
            return self._run_blocking_fallback(command, actual_timeout)

        # 1. Use Persistent Session
        manager = ShellManager.get_instance()
        session = manager.get_or_create_session(self.session_id, str(self.base_dir))
        
        # 2. Send Command
        ws = session.write(command)
        if "Error" in ws: return ws

        # 3. Smart Read (Wait for Exit OR Idle)
        # Idle timeout indicates "The stream paused, maybe waiting for input?"
        output, is_finished = session.read_until_idle(total_timeout=actual_timeout, idle_timeout=2.0)
        
        if is_finished:
            # Process finished naturally
            exit_code = session.process.returncode
            return self._format_output(output, "", exit_code)
        else:
            # Stopped due to Idle (Interactive Prompt?) or Total Timeout (Long running)
            return (
                f"⚠️ COMMAND ACTIVE (Paused/Idle)\n"
                f"The command is still running but stopped producing output (likely waiting for input).\n"
                f"--- OUTPUT SO FAR ---\n{output}\n"
                f"👉 ACTION REQUIRED: If it's asking for input, use 'send_shell_input'. If it's just slow, use 'read_shell_output' to monitor."
            )

    def _run_blocking_fallback(self, command: str, timeout: int) -> str:
        """Legacy blocking method for when no session_id is present."""
        logger.info(f"🐚 RUN (Fallback): {command}")
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if self.is_windows else 0
        start_new_session = not self.is_windows
        process = None
        try:
            process = subprocess.Popen(
                command, cwd=str(self.base_dir), shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=creationflags, start_new_session=start_new_session
            )
            stdout, stderr = process.communicate(timeout=timeout)
            return self._format_output(stdout, stderr, process.returncode)
        except subprocess.TimeoutExpired as e:
            if process: self._kill_process_tree(process.pid)
            return f"❌ TIMEOUT (>{timeout}s). Partial: {e.stdout}"
        except Exception as e:
            if process: self._kill_process_tree(process.pid)
            return f"❌ SYSTEM ERROR: {str(e)}"

    def _format_output(self, stdout, stderr, exit_code):
        output_parts = []
        if stdout and stdout.strip(): output_parts.append(f"--- STDOUT ---\n{stdout.strip()}")
        if stderr and stderr.strip(): output_parts.append(f"--- STDERR ---\n{stderr.strip()}")
        full_output = "\n".join(output_parts) if output_parts else "(No output)"
        return f"✅ SUCCESS (Exit Code 0)\n{full_output}" if exit_code == 0 else f"❌ FAILED (Exit Code {exit_code})\n{full_output}"

    # --- Interactive / Persistent Session Tools ---
    def start_interactive_session(self, command: str) -> str:
        """
        Starts a persistent, non-blocking shell session (e.g., 'npm run dev', 'python script.py').
        Use this when you need to send input later or monitor a long-running server.
        
        Args:
            command (str): The command to start.
        """
        if not self.session_id:
            return "❌ Error: Tool not initialized with valid session_id."

        manager = ShellManager.get_instance()
        session = manager.get_or_create_session(self.session_id, str(self.base_dir))
        
        # Start the command (clears previous if any)
        # Note: ShellSession currently just launches a generic shell. We assume we are typing into that shell.
        # However, the user might expect 'start_interactive_session("npm start")' to RUN it.
        # So we should write the command immediately.
        
        result = session.write(command)
        
        # Wait a brief moment for immediate output (e.g. startup errors)
        import time
        time.sleep(1.0) 
        output = session.read(timeout_sec=0)
        
        return f"Interactive Session Started.\nCommand Sent: {command}\nResult: {result}\n\n--- INITIAL OUTPUT ---\n{output}\n\n> Use 'send_shell_input' to interact or 'read_shell_output' to monitor."

    def send_shell_input(self, input_text: str) -> str:
        """
        Sends text input to the active interactive shell session.
        Useful for answering prompts (y/n, names, etc.) or sending CTRL+C.
        
        Args:
            input_text (str): The text to send (newline is added automatically).
        """
        if not self.session_id: return "❌ No Session ID."
        manager = ShellManager.get_instance()
        session = manager.get_session(self.session_id)
        if not session: return "❌ No active shell session found. Use 'start_interactive_session' first."
        
        res = session.write(input_text)
        return f"{res}\n(Call 'read_shell_output' to see response)"

    def read_shell_output(self, wait_seconds: float = 1.0) -> str:
        """
        Reads the latest output from the active shell session without blocking.
        
        Args:
            wait_seconds (float): How long to accumulate output before returning (default 1.0s).
        """
        if not self.session_id: return "❌ No Session ID."
        manager = ShellManager.get_instance()
        session = manager.get_session(self.session_id)
        if not session: return "❌ No active shell session found."
        
        return session.read(timeout_sec=wait_seconds)

    def close_shell_session(self) -> str:
        """Kills the active interactive shell session."""
        if not self.session_id: return "❌ No Session ID."
        manager = ShellManager.get_instance()
        manager.close_session(self.session_id)
        return "✅ Interactive session closed."
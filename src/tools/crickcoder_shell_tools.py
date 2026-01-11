import subprocess
import platform
import logging
import os
import signal
from pathlib import Path
from typing import Optional, Union, List
from agno.tools import Toolkit 

logger = logging.getLogger(__name__)

class CrickCoderShellTools(Toolkit):
    def __init__(
        self,
        base_dir: Optional[Union[Path, str]] = None,
        timeout_seconds: int = 60,
        
        # 👇 NEW: Safety Flag
        enable_confirmation: bool = False, 
        **kwargs,
    ):
        # Determine which tools need native API confirmation
        # If enabled, Agno will automatically PAUSE execution before 'run_shell_command'
        confirmation_tools = ["run_shell_command"] if enable_confirmation else []

        super().__init__(
            name="shell_tools", 
            requires_confirmation_tools=confirmation_tools, # <--- Agno Native Logic
            **kwargs
        )
        
        # Path setup
        self.base_dir = Path(base_dir).resolve() if base_dir else Path.cwd()
        self.timeout = timeout_seconds
        
        # OS Detection for specific kill strategies
        self.is_windows = platform.system() == "Windows"
        
        # Register the function
        self.register(self.run_shell_command)

    def _kill_process_tree(self, pid: int):
        """
        Kills the process and all its children aggressively.
        Essential to avoid "Zombie" processes on Windows with shell=True.
        """
        if self.is_windows:
            try:
                # /F = Force, /T = Tree (children), /PID = Process ID
                subprocess.run(
                    f"taskkill /F /T /PID {pid}", 
                    shell=True, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                logger.error(f"Failed to kill Windows process tree: {e}")
        else:
            try:
                # On Linux/Mac we kill the Process Group
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception as e:
                logger.error(f"Failed to kill Unix process group: {e}")

    def run_shell_command(self, command: str, timeout: Optional[int] = None) -> str:
        """
        Executes a shell command with robust TIMEOUT handling and Clean Kill.
        
        If enable_confirmation=True, this code will NOT start until
        the API calls continue_run().
        
        Args:
            command (str): The command to execute.
            timeout (int): Specific timeout (optional).
        """
        actual_timeout = timeout if timeout is not None else self.timeout
        
        logger.info(f"🐚 RUN (T={actual_timeout}s): {command} | CWD: {self.base_dir}")

        # Specific configuration to handle process groups (for kill)
        creationflags = 0
        start_new_session = False
        
        if self.is_windows:
            # On Windows, CREATE_NEW_PROCESS_GROUP allows sending signals to the group
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            # On Unix, setsid creates a new session group
            start_new_session = True

        process = None
        try:
            # Using Popen instead of run for total control
            process = subprocess.Popen(
                command,
                cwd=str(self.base_dir),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                start_new_session=start_new_session
            )

            # communicate() waits for completion or timeout
            stdout, stderr = process.communicate(timeout=actual_timeout)
            exit_code = process.returncode

            return self._format_output(stdout, stderr, exit_code)

        except subprocess.TimeoutExpired:
            logger.warning(f"⏳ TIMEOUT ({actual_timeout}s): Killing process tree...")
            
            # 1. Kill the entire process tree
            if process:
                self._kill_process_tree(process.pid)
            
            # 2. Try to recover partial output to understand where it got stuck
            partial_out, partial_err = "", ""
            if process:
                try:
                    # Best-effort attempt to read buffer
                    if process.stdout: partial_out = process.stdout.read()
                    if process.stderr: partial_err = process.stderr.read()
                except:
                    pass

            return (
                f"❌ TIMEOUT ERROR\n"
                f"The command exceeded the limit of {actual_timeout} seconds and was forcibly terminated.\n"
                f"--- PARTIAL STDOUT ---\n{partial_out}\n"
                f"--- PARTIAL STDERR ---\n{partial_err}"
            )

        except Exception as e:
            # Fallback for generic python crashes
            if process:
                self._kill_process_tree(process.pid)
            logger.error(f"💥 SYSTEM ERROR: {e}")
            return f"❌ SYSTEM ERROR: {str(e)}"

    def _format_output(self, stdout, stderr, exit_code):
        """Formats output to be readable for the LLM"""
        output_parts = []
        if stdout and stdout.strip():
            output_parts.append(f"--- STDOUT ---\n{stdout.strip()}")
        if stderr and stderr.strip():
            output_parts.append(f"--- STDERR ---\n{stderr.strip()}")
        
        full_output = "\n".join(output_parts) if output_parts else "(No output)"

        if exit_code == 0:
            return f"✅ SUCCESS (Exit Code 0)\n{full_output}"
        else:
            return f"❌ FAILED (Exit Code {exit_code})\n{full_output}"
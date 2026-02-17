import subprocess
import threading
import queue
import time
import os
import signal
import platform
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class ShellSession:
    """
    Represents a persistent shell session running in a background process.
    Captures stdout/stderr continuously via daemon threads.
    """
    def __init__(self, session_id: str, cwd: str):
        self.session_id = session_id
        self.cwd = cwd
        self.process: Optional[subprocess.Popen] = None
        self.stdout_queue = queue.Queue()
        self.stderr_queue = queue.Queue()
        self.is_active = False
        self.history: list[str] = [] # Keep a small history of commands
        
        self._start_process()

    def _start_process(self):
        """Starts the subprocess with non-blocking I/O threads."""
        try:
            # Windows-specific flags to allow killing the whole process tree later
            creationflags = 0
            if platform.system() == "Windows":
                 creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            
            self.process = subprocess.Popen(
                # Use cmd.exe on Windows for better compatibility, or just shell=True default
                "cmd.exe" if platform.system() == "Windows" else "/bin/bash", 
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0, # Unbuffered
                creationflags=creationflags,
                shell=False # We are running the shell explicitly
            )
            self.is_active = True
            
            # Start monitoring threads
            threading.Thread(target=self._enqueue_output, args=(self.process.stdout, self.stdout_queue), daemon=True).start()
            threading.Thread(target=self._enqueue_output, args=(self.process.stderr, self.stderr_queue), daemon=True).start()
            
            logger.info(f"[SHELL] Shell Session {self.session_id} started in {self.cwd}")
            
        except Exception as e:
            logger.error(f"Failed to start shell session: {e}")
            self.is_active = False

    def _enqueue_output(self, out, q):
        """Reads output line by line and puts it in the queue."""
        for line in iter(out.readline, ''):
            q.put(line)
        out.close()

    def write(self, command: str):
        """Writes a command to the shell's stdin."""
        if not self.is_active or not self.process:
            return "[ERROR] Error: Shell is not active."
        
        try:
            if not command.endswith("\n"):
                command += "\n"
                
            self.process.stdin.write(command)
            self.process.stdin.flush()
            self.history.append(command.strip())
            return "[OK] Command sent."
        except Exception as e:
            logger.error(f"Error writing to shell: {e}")
            return f"[ERROR] Error: {str(e)}"

    def read(self, timeout_sec: float = 0.5) -> str:
        """Reads all currently available output from queues."""
        if not self.is_active:
            return "Shell session is inactive."

        # Wait a bit for output to accumulate if requested
        if timeout_sec > 0:
            time.sleep(timeout_sec)
        
        output = []
        
        # Read Stdout
        while not self.stdout_queue.empty():
            try:
                line = self.stdout_queue.get_nowait()
                output.append(line)
            except queue.Empty:
                break
                
        # Read Stderr
        stderr_lines = []
        while not self.stderr_queue.empty():
            try:
                line = self.stderr_queue.get_nowait()
                stderr_lines.append(line)
            except queue.Empty:
                break
                
        result = ""
        if output:
            result += "".join(output)
        if stderr_lines:
            result += "\n--- STDERR ---\n" + "".join(stderr_lines)
            
        return result if result else "(No new output)"

    def read_until_idle(self, total_timeout: float = 60.0, idle_timeout: float = 2.0, stream_callback=None) -> Tuple[str, bool]:
        """
        Reads output until:
        1. Process exits (returns (output, True))
        2. Total timeout reached (returns (output, False))
        3. No new output for idle_timeout (returns (output, False)) - Indicates waiting for input
        
        Args:
            total_timeout: Max time to wait.
            idle_timeout: Max time to wait for new output.
            stream_callback: Optional function(str) to call with new output chunks.

        Returns:
            (collected_output, is_process_finished)
        """
        start_time = time.time()
        last_new_data_time = time.time()
        collected_parts = []
        
        while True:
            # 1. Check Process Exit
            if self.process.poll() is not None:
                # Process finished, grab remaining output
                final_chunk = self.read(timeout_sec=0)
                if final_chunk != "(No new output)":
                    if stream_callback: stream_callback(final_chunk)
                    collected_parts.append(final_chunk)
                return "\n".join(collected_parts), True

            # 2. Check Total Timeout
            if (time.time() - start_time) > total_timeout:
                return "\n".join(collected_parts), False

            # 3. Read available data
            chunk = self.read(timeout_sec=0.1) # Small wait to allow buffer fill
            
            if chunk != "(No new output)":
                if stream_callback: stream_callback(chunk)
                collected_parts.append(chunk)
                last_new_data_time = time.time() # Reset idle timer
            else:
                # No data received in this cycle. Check Idle Timeout.
                # Only if we have some previous data? No, valid to be idle immediately if slow start, 
                # but usually we want to see if it STOPS producing output.
                # If we haven't received ANY data yet, we might want to wait at least a bit longer?
                # The total_timeout handles 'forever hanging without output'.
                # The idle_timeout handles 'burst of output then stop'.
                
                if (time.time() - last_new_data_time) > idle_timeout:
                    return "\n".join(collected_parts), False


    def kill(self):
        """Terminates the process tree."""
        if self.process:
            try:
                if platform.system() == "Windows":
                    subprocess.run(f"taskkill /F /T /PID {self.process.pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except Exception as e:
                logger.warning(f"Error killing shell process: {e}")
        self.is_active = False


class ShellManager:
    """
    Singleton Manager for active shell sessions.
    """
    _instance = None
    _sessions: Dict[str, ShellSession] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ShellManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ShellManager()
        return cls._instance

    def get_or_create_session(self, session_id: str, cwd: str) -> ShellSession:
        if session_id not in self._sessions or not self._sessions[session_id].is_active:
            # Cleanup old dead session if exists
            if session_id in self._sessions:
                try: self._sessions[session_id].kill() 
                except: pass
            
            # Create new
            self._sessions[session_id] = ShellSession(session_id, cwd)
        
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> Optional[ShellSession]:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str):
        if session_id in self._sessions:
            self._sessions[session_id].kill()
            del self._sessions[session_id]

import json
from pathlib import Path
from typing import Any, List, Optional, Tuple

from agno.tools import Toolkit
from agno.utils.log import log_debug, log_error


class CrickCoderFileTools(Toolkit):
    def __init__(
        self,
        base_dir: Optional[Path] = None,
        enable_save_file: bool = True,
        enable_read_file: bool = True,
        enable_delete_file: bool = False,
        enable_list_files: bool = True,
        enable_search_files: bool = True,
        enable_read_file_chunk: bool = True,
        enable_replace_file_chunk: bool = True,
        expose_base_directory: bool = False,
        max_file_length: int = 10000000,
        max_file_lines: int = 100000,
        line_separator: str = "\n",
        all: bool = False,
        
       
        enable_confirmation: bool = False, 
        **kwargs,
    ):
        self.base_dir: Path = base_dir or Path.cwd()
        self.base_dir = self.base_dir.resolve()

        tools: List[Any] = []
        
        # List of functions that require confirmation
        tools_needing_confirmation: List[str] = []

        self.max_file_length = max_file_length
        self.max_file_lines = max_file_lines
        self.line_separator = line_separator
        self.expose_base_directory = expose_base_directory

        # --- REGISTER TOOLS ---
        
        if all or enable_save_file:
            tools.append(self.save_file)
            tools.append(self.append_to_file)
            if enable_confirmation: 
                tools_needing_confirmation.append("save_file")
                tools_needing_confirmation.append("append_to_file")

        if all or enable_read_file:
            tools.append(self.read_file)
            # Read is safe, usually does not need confirmation

        if all or enable_list_files:
            tools.append(self.list_files)
            # List is safe

        if all or enable_search_files:
            tools.append(self.search_files)
            # Search is safe

        if all or enable_delete_file:
            tools.append(self.delete_file)
            if enable_confirmation: tools_needing_confirmation.append("delete_file")

        if all or enable_read_file_chunk:
            tools.append(self.read_file_chunk)

        if all or enable_replace_file_chunk:
            tools.append(self.replace_file_chunk)
            if enable_confirmation: tools_needing_confirmation.append("replace_file_chunk")

        # --- PARENT INITIALIZATION ---
        # Pass the dynamic list to Agno
        super().__init__(
            name="file_tools", 
            tools=tools, 
            requires_confirmation_tools=tools_needing_confirmation,
            **kwargs
        )

    # ... (Il resto dei metodi save_file, read_file, etc. rimane IDENTICO al tuo codice) ...
    # Ricopio solo i metodi chiave per completezza, ma la logica interna non cambia.

    def save_file(self, contents: str, file_name: str, overwrite: bool = True, encoding: str = "utf-8") -> str:
        """Saves the contents to a file called `file_name`."""
        try:
            safe, file_path = self.check_escape(file_name)
            if not (safe):
                log_error(f"Attempted to save file: {file_name}")
                return "Error saving file"
            
            # --- SHADOW SNAPSHOT ---
            try:
                from src.core.runtime.shadow_workspace import ShadowWorkspace
                ShadowWorkspace.get_instance().snapshot(str(file_path))
            except Exception as e:
                log_error(f"Shadow Snapshot failed: {e}")
            # -----------------------

            log_debug(f"Saving contents to {file_path}")
            if not file_path.parent.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)
            if file_path.exists() and not overwrite:
                return f"File {file_name} already exists"
            file_path.write_text(contents, encoding=encoding)
            log_debug(f"Saved: {file_path}")
            return str(file_name)
        except Exception as e:
            log_error(f"Error saving to file: {e}")
            return f"Error saving to file: {e}"

    def append_to_file(self, contents: str, file_name: str, encoding: str = "utf-8") -> str:
        """Appends the contents to a file called `file_name`."""
        try:
            safe, file_path = self.check_escape(file_name)
            if not safe:
                log_error(f"Attempted to append to unsafe file: {file_name}")
                return "Error: Path is outside base directory."
            
            if not file_path.parent.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # --- SHADOW SNAPSHOT ---
            try:
                from src.core.runtime.shadow_workspace import ShadowWorkspace
                ShadowWorkspace.get_instance().snapshot(str(file_path))
            except Exception as e:
                log_error(f"Shadow Snapshot failed: {e}")
            # -----------------------

            with open(file_path, "a", encoding=encoding) as f:
                f.write(contents)
            
            log_debug(f"Appended to: {file_path}")
            return f"Appended to {file_name} successfully."
        except Exception as e:
            log_error(f"Error appending to file: {e}")
            return f"Error appending to file: {e}"

    def replace_file_chunk(self, file_name: str, search_text: str, replace_text: str, encoding: str = "utf-8") -> str:
        """Replaces a specific block of text in a file with new text."""
        try:
            safe, file_path = self.check_escape(file_name)
            if not safe:
                return f"Error: Path '{file_name}' is outside base directory."
            
            if not file_path.exists():
                return f"Error: File '{file_name}' does not exist."

            content = file_path.read_text(encoding=encoding)

            if search_text not in content:
                return (
                    f"Error: The 'search_text' block was not found in '{file_name}'.\n"
                    "CRITICAL: You must provide the text EXACTLY as it appears."
                )

            count = content.count(search_text)
            if count > 1:
                return (
                    f"Error: The 'search_text' block appears {count} times.\n"
                    "Action: Please include more context."
                )

            new_content = content.replace(search_text, replace_text, 1)

            # --- SHADOW SNAPSHOT ---
            try:
                from src.core.runtime.shadow_workspace import ShadowWorkspace
                ShadowWorkspace.get_instance().snapshot(str(file_path))
            except Exception as e:
                log_error(f"Shadow Snapshot failed: {e}")
            # -----------------------

            file_path.write_text(new_content, encoding=encoding)
            
            log_debug(f"Successfully patched {file_name}")
            return f"Success: Updated {file_name}."

        except Exception as e:
            log_error(f"Error updating {file_name}: {e}")
            return f"System Error: {str(e)}"

    def delete_file(self, file_name: str) -> str:
        """Deletes a file"""
        safe, path = self.check_escape(file_name)
        try:
            if safe:
                if path.is_dir():
                    path.rmdir()
                    return ""
                path.unlink()
                return ""
            else:
                log_error(f"Attempt to delete file outside base_dir: {file_name}")
                return "Incorrect file_name"
        except Exception as e:
            log_error(f"Error removing {file_name}: {e}")
            return f"Error removing file: {e}"

    # ... (read_file, list_files, search_files, check_escape rimangono uguali) ...
    def read_file(self, file_name: str, encoding: str = "utf-8") -> str:
        """Reads the contents of the file `file_name`."""
        try:
            safe, file_path = self.check_escape(file_name)
            if not (safe): return "Error reading file"
            contents = file_path.read_text(encoding=encoding)
            if len(contents) > self.max_file_length: return "Error: file too long"
            return str(contents)
        except Exception as e:
            return f"Error reading file: {e}"

    def list_files(self, **kwargs) -> str:
        """Lists files in the base directory or a specific subdirectory."""
        directory = kwargs.get("directory", ".")
        try:
            safe, d = self.check_escape(directory)
            if safe:
                return json.dumps([str(p.relative_to(self.base_dir)) for p in d.iterdir()], indent=4)
            return "{}"
        except Exception:
            return "{}"

    def search_files(self, pattern: str) -> str:
        """Searches for files matching the glob pattern."""
        try:
            matching_files = list(self.base_dir.glob(pattern))
            file_paths = [str(p.relative_to(self.base_dir)) for p in matching_files]
            return json.dumps({"files": file_paths}, indent=2)
        except Exception as e:
            return f"Error: {e}"
            
    def read_file_chunk(self, file_name: str, start_line: int, end_line: int, encoding: str = "utf-8") -> str:
        """Reads a specific chunk of lines from a file."""
        try:
            safe, file_path = self.check_escape(file_name)
            if not safe: return "Error"
            contents = file_path.read_text(encoding=encoding)
            lines = contents.split(self.line_separator)
            # Adjust for 1-based indexing if necessary, but assuming 0-based or matching usage
            # Usually users expect 1-based, but code uses start_line : end_line + 1
            return self.line_separator.join(lines[start_line : end_line + 1])
        except Exception as e:
            return f"Error: {e}"

    def check_escape(self, relative_path: str) -> Tuple[bool, Path]:
        d = self.base_dir.joinpath(Path(relative_path)).resolve()
        if self.base_dir == d: return True, d
        try:
            d.relative_to(self.base_dir)
        except ValueError:
            return False, self.base_dir
        return True, d
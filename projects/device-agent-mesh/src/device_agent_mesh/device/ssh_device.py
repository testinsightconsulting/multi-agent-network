"""Generic SSH device interface with prompt handling."""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

import paramiko

from device_agent_mesh.device.device_interface import DeviceInterface


class GenericSshDeviceInterface(DeviceInterface):
    """DeviceInterface implementation for generic network devices over SSH."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        timeout: float = 10.0,
        prompt_regex: str = r"[>#]\s*$",
        enable_command: Optional[str] = None,
        enable_password: Optional[str] = None,
        session_prep_commands: Optional[List[str]] = None,
        prompt_handlers: Optional[List[dict]] = None,
        config_command: str = "show running-config",
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.prompt_regex = re.compile(prompt_regex)
        self.enable_command = enable_command
        self.enable_password = enable_password
        self.session_prep_commands = session_prep_commands or []
        self._prompt_handlers: List[Tuple[re.Pattern, str]] = []
        if prompt_handlers:
            self.update_prompt_handlers(prompt_handlers)
        self.config_command = config_command
        self._client: Optional[paramiko.SSHClient] = None
        self._channel: Optional[paramiko.Channel] = None

    def _ensure_connected(self) -> None:
        if self._client is not None and self._channel is not None:
            return

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Try connecting with standard options
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False,
            )
            self._client = client
            self._channel = client.invoke_shell()
        except (paramiko.AuthenticationException, paramiko.SSHException) as e:
            # Arista often allows 'keyboard-interactive' but rejects standard 'password'
            # We try a dedicated transport for fine-grained auth control
            try:
                transport = paramiko.Transport((self.host, self.port))
                transport.start_client()
                
                # Check what the server allows
                allowed = transport.get_allowed_auths(self.username)
                
                if 'keyboard-interactive' in allowed:
                    def handler(title, instructions, prompt_list):
                        # Some devices send complex instructions; we just return password for all prompts
                        return [self.password] * len(prompt_list)
                    transport.auth_interactive(self.username, handler)
                elif 'password' in allowed:
                    transport.auth_password(self.username, self.password)
                
                if transport.is_authenticated():
                    self._client = client # Placeholder
                    self._channel = transport.open_session()
                    self._channel.get_pty()
                    self._channel.invoke_shell()
                else:
                    transport.close()
                    raise e
            except Exception as e2:
                # If everything fails, raise the original auth exception
                raise e

        # Wait for initial prompt
        self._read_until_prompt()

        # Optional: enter enable mode
        if self.enable_command:
            self._send_command(self.enable_command, expect_password=True)

        # Optional: run session prep commands (e.g. disable paging)
        for cmd in self.session_prep_commands:
            self._send_command(cmd)

    def _read_until_prompt(self, expect_password: bool = False, timeout: Optional[float] = None) -> str:
        if self._channel is None:
            return ""
        output = ""
        current_timeout = timeout or self.timeout
        start = time.time()
        last_activity = start
        handled = set()
        
        while True:
            now = time.time()
            # Absolute timeout for the entire operation
            if now - start > current_timeout * 3: # allow up to 3x base timeout for very long streams
                break
            # Activity timeout (no data for X seconds)
            if now - last_activity > current_timeout:
                break
                
            if self._channel.recv_ready():
                chunk = self._channel.recv(4096).decode(errors="ignore")
                if chunk:
                    output += chunk
                    last_activity = time.time() # Reset activity timer
                
                # Handle enable password prompt
                if expect_password and self.enable_password and re.search(r"password[: ]*$", output, re.IGNORECASE):
                    self._channel.send(self.enable_password + "\n")
                    expect_password = False
                    last_activity = time.time()
                # Handle paging prompt
                if "--More--" in output or "More" in output:
                    self._channel.send(" ")
                    last_activity = time.time()
                # Handle known prompts from handlers
                for pattern, response in self._prompt_handlers:
                    if pattern.pattern in handled:
                        continue
                    match = pattern.search(output)
                    if match:
                        # Extract the matched text to remove it later if it's an error/prompt
                        self._channel.send(response)
                        handled.add(pattern.pattern)
                        last_activity = time.time()
                
                # Prompt check
                lines = output.splitlines()
                if lines and self.prompt_regex.search(lines[-1]):
                    break
            else:
                time.sleep(0.1)
        
        # Post-process: Remove handled prompt/error messages from output
        # We use a while loop to handle repeated prompts if they were sent
        cleaned_output = output
        for pattern, _ in self._prompt_handlers:
            # We want to remove the entire line containing the prompt to be clean
            # or just the matched pattern. Here we'll do the pattern.
            cleaned_output = pattern.sub("", cleaned_output)
        
        # More aggressive cleaning for known VyOS/Linux specific messages that confuse the agent
        ephemeral_messages = [
            "Log file is already in use (press RETURN)",
            "Log file is already in use",
            "(press RETURN)",
            "--More--",
            "More",
        ]
        for msg in ephemeral_messages:
            cleaned_output = cleaned_output.replace(msg, "")
        
        return cleaned_output.strip()

    def _send_command(self, command: str, expect_password: bool = False) -> str:
        if self._channel is None:
            raise RuntimeError("SSH channel not connected")
        self._channel.send(command + "\n")
        return self._read_until_prompt(expect_password=expect_password)

    def get_configuration(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get running config (optionally a section) via SSH."""
        if section:
            # Most devices use 'show running-config section X' or similar. 
            # This is a heuristic that can be improved.
            command = f"{self.config_command} section {section}"
        else:
            command = self.config_command
        output = self.execute_command(command)
        return {"command": command, "output": output}

    def execute_command(self, command: str) -> str:
        """Execute a CLI command over SSH and return raw output."""
        self._ensure_connected()
        return self._send_command(command)

    def update_prompt_handlers(self, handlers: List[dict]) -> None:
        """Add or replace prompt handlers. Each handler: {pattern, response}."""
        self._prompt_handlers = []
        for h in handlers:
            pattern = h.get("pattern")
            response = h.get("response", "")
            if pattern:
                self._prompt_handlers.append((re.compile(pattern), response))

    def list_prompt_handlers(self) -> List[dict]:
        """Return current prompt handlers."""
        return [{"pattern": p.pattern, "response": r} for p, r in self._prompt_handlers]

    def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None
        if self._client is not None:
            self._client.close()
            self._client = None

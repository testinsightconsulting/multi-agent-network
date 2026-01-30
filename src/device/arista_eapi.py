"""Arista EOS eAPI device interface (optional real-device integration)."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx

from src.device.device_interface import DeviceInterface


class AristaEapiDeviceInterface(DeviceInterface):
    """DeviceInterface implementation for Arista EOS eAPI."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        use_https: bool = True,
        port: Optional[int] = None,
        verify_ssl: bool = False,
        timeout: float = 10.0,
    ):
        scheme = "https" if use_https else "http"
        if port is None:
            port = 443 if use_https else 80
        self.endpoint = f"{scheme}://{host}:{port}/command-api"
        self.auth = (username, password)
        self.verify_ssl = verify_ssl
        self.timeout = timeout

    def get_configuration(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get running config (optionally a section) via eAPI."""
        if section:
            command = f"show running-config section {section}"
        else:
            command = "show running-config"
        output = self.execute_command(command)
        # Return raw output as a dict for consistency
        return {"command": command, "output": output}

    def execute_command(self, command: str) -> str:
        """Execute an EOS CLI command over eAPI."""
        payload = {
            "jsonrpc": "2.0",
            "method": "runCmds",
            "params": {
                "version": 1,
                "cmds": [command],
                "format": "json",
            },
            "id": 1,
        }
        response = httpx.post(
            self.endpoint,
            json=payload,
            auth=self.auth,
            verify=self.verify_ssl,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"eAPI error: {data['error']}")
        # Return JSON output of first command as a formatted string
        result = data.get("result", [{}])[0]
        return json.dumps(result, indent=2)

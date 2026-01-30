"""Device interface abstractions"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import yaml


class DeviceInterface(ABC):
    """Abstract interface for device communication"""
    
    @abstractmethod
    def get_configuration(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get device configuration"""
        pass
    
    @abstractmethod
    def execute_command(self, command: str) -> str:
        """Execute a command on the device"""
        pass


class SimulatedDevice(DeviceInterface):
    """Simulated device for PoC (replace with real SSH/API implementation)"""
    
    def __init__(self, device_name: str, config_file: str):
        self.device_name = device_name
        self.config_file = config_file
        self._config_cache = None
    
    def get_configuration(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration from file (simulated)"""
        if self._config_cache is None:
            try:
                with open(self.config_file, 'r') as f:
                    self._config_cache = yaml.safe_load(f)
            except FileNotFoundError:
                self._config_cache = {
                    "device": self.device_name,
                    "configuration": "No configuration file found"
                }
        
        if section:
            return self._config_cache.get(section, {})
        return self._config_cache
    
    def execute_command(self, command: str) -> str:
        """Simulate command execution"""
        # In real implementation, this would SSH/API to device
        config = self.get_configuration()
        
        # Simple command simulation
        if "show" in command.lower() and "config" in command.lower():
            return f"Configuration for {self.device_name}:\n{yaml.dump(config, default_flow_style=False)}"
        elif "show" in command.lower() and "bgp" in command.lower():
            return f"BGP Status for {self.device_name}:\nNeighbors: 2\nRoutes: 150\nState: Established"
        elif "show" in command.lower() and "interface" in command.lower():
            return f"Interfaces for {self.device_name}:\nGigabitEthernet0/0: UP\nGigabitEthernet0/1: UP"
        else:
            return f"Simulated output for command: {command}\nDevice: {self.device_name}"


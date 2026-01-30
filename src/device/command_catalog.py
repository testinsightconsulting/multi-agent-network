"""Command catalog per vendor/model for device specialists."""
from typing import Dict, List, Optional


COMMAND_CATALOG: Dict[str, Dict[str, str]] = {
    "generic": {
        "show_config": "show running-config",
        "show_interfaces": "show interfaces",
        "show_bgp": "show ip bgp summary",
        "show_ospf": "show ip ospf neighbor",
        "show_version": "show version",
    },
    "cisco": {
        "show_config": "show running-config",
        "show_interfaces": "show ip interface brief",
        "show_bgp": "show ip bgp",
        "show_ospf": "show ip ospf neighbor",
        "show_version": "show version",
        "show_vlans": "show vlan brief",
        "show_stp": "show spanning-tree",
    },
    "juniper": {
        "show_config": "show configuration",
        "show_interfaces": "show interfaces terse",
        "show_bgp": "show bgp summary",
        "show_ospf": "show ospf neighbor",
        "show_version": "show version",
    },
    "arista": {
        "show_config": "show running-config",
        "show_interfaces": "show ip interface brief",
        "show_bgp": "show ip bgp summary",
        "show_ospf": "show ip ospf neighbor",
        "show_version": "show version",
        "show_platform": "show platform",
    },
    "spirent": {
        "show_config": "show configuration",
        "show_interfaces": "show interfaces",
        "show_status": "show status",
        "show_version": "show version",
    },
    "vyos": {
        "show_config": "show configuration",
        "show_interfaces": "show interfaces",
        "show_bgp": "show ip bgp summary",
        "show_ospf": "show ip ospf neighbor",
        "show_version": "show version",
    },
}

SESSION_PREP_COMMANDS: Dict[str, List[str]] = {
    "generic": ["terminal length 0"],
    "cisco": ["terminal length 0"],
    "arista": ["terminal length 0"],
    "juniper": ["set cli screen-length 0"],
    "spirent": [],
    "vyos": ["set console page 0"],
}

ENABLE_COMMAND: Dict[str, str] = {
    "cisco": "enable",
    "arista": "enable",
    "juniper": "",  # typically not required
    "spirent": "",
    "generic": "",
}


_VENDOR_KEYWORDS: Dict[str, List[str]] = {
    "cisco": ["cisco", "ios", "nexus"],
    "juniper": ["juniper", "junos"],
    "arista": ["arista", "eos"],
    "vyos": ["vyos"],
    "spirent": ["spirent", "stc", "vstc"],
}


def resolve_vendor_key(device_type: str) -> str:
    """Resolve a canonical vendor key from a descriptive string (e.g. 'VyOS_Router' -> 'vyos')."""
    if not device_type:
        return "generic"
    
    val = device_type.lower()
    # First try exact match
    if val in COMMAND_CATALOG:
        return val
    
    # Then try keyword search
    for key, keywords in _VENDOR_KEYWORDS.items():
        if any(kw in val for kw in keywords):
            return key
            
    return "generic"


def resolve_vendor_from_metadata(metadata: List[Optional[str]]) -> str:
    """Try to resolve vendor key from a list of metadata strings, ordered by priority."""
    for text in metadata:
        if text:
            resolved = resolve_vendor_key(text)
            if resolved != "generic":
                return resolved
    return "generic"


def get_commands_for_device(device_type: str, model: str = "") -> Dict[str, str]:
    """Return command catalog for a vendor/model."""
    key = resolve_vendor_key(device_type)
    commands = COMMAND_CATALOG.get(key, COMMAND_CATALOG["generic"]).copy()
    return commands


def get_session_prep_for_device(device_type: str) -> List[str]:
    """Return session prep commands (e.g., disable paging) for a vendor."""
    key = resolve_vendor_key(device_type)
    return SESSION_PREP_COMMANDS.get(key, SESSION_PREP_COMMANDS["generic"]).copy()


def get_enable_command_for_device(device_type: str) -> str:
    """Return enable command for a vendor (if required)."""
    key = resolve_vendor_key(device_type)
    return ENABLE_COMMAND.get(key, "")

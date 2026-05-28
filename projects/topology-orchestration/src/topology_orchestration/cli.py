"""CLI to inspect orchestration topology YAML files."""
import json

import click

from topology_orchestration.topology_loader import load_topology


@click.command()
@click.argument("topology_file", type=click.Path(exists=True))
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON summary.")
def main(topology_file: str, as_json: bool) -> None:
    """Inspect a Velocity/TOSCA topology and list discovered devices."""
    topo = load_topology(topology_file)
    if as_json:
        payload = {
            "name": topo.name,
            "device_count": len(topo.devices),
            "devices": [
                {
                    "inventory_id": d.inventory_id,
                    "inventory_name": d.inventory_name,
                    "make": d.make,
                    "model": d.model,
                    "ip_address": d.ip_address,
                    "agent_id": d.agent_id,
                }
                for d in topo.devices
            ],
        }
        click.echo(json.dumps(payload, indent=2))
        return

    click.echo(f"Topology: {topo.name}")
    click.echo(f"Devices: {len(topo.devices)}")
    for device in topo.devices:
        click.echo(
            f"  - {device.inventory_name} ({device.make} {device.model}) "
            f"inventory_id={device.inventory_id} ip={device.ip_address or 'n/a'}"
        )


if __name__ == "__main__":
    main()

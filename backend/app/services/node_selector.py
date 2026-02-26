import logging

from app.services.proxmox import ProxmoxService

logger = logging.getLogger(__name__)


class NodeSelector:
    """Selects the best Proxmox node for VM placement."""

    def __init__(self, proxmox: ProxmoxService):
        self.proxmox = proxmox

    def select_node(self, strategy: str = "least_memory") -> str:
        """Select a node based on the given strategy.

        Strategies:
        - least_memory: Pick the node with the most free RAM (lowest usage ratio).
        """
        nodes = self.proxmox.get_nodes()
        online_nodes = [n for n in nodes if n.get("status") == "online"]

        if not online_nodes:
            raise RuntimeError("No online Proxmox nodes found")

        if len(online_nodes) == 1:
            return online_nodes[0]["node"]

        if strategy == "least_memory":
            best = min(
                online_nodes,
                key=lambda n: n.get("mem", 0) / max(n.get("maxmem", 1), 1),
            )
            return best["node"]

        return online_nodes[0]["node"]

from typing import Dict, List, Type, Union

from langflow.graph.edge.base import Edge
from langflow.graph.graph.constants import NODE_TYPE_MAP
from langflow.graph.node.base import Node
from langflow.graph.node.types import (
    FileToolNode,
    LLMNode,
    ToolkitNode,
)
from langflow.interface.tools.constants import FILE_TOOLS
from langflow.utils import payload


class Graph:
    """A class representing a graph of nodes and edges."""

    def __init__(
        self,
        nodes: List[Dict[str, Union[str, Dict[str, Union[str, List[str]]]]]],
        edges: List[Dict[str, str]],
    ) -> None:
        self._nodes = nodes
        self._edges = edges
        self._build_graph()

    def _build_graph(self) -> None:
        """Builds the graph from the nodes and edges."""
        self.nodes = self._build_nodes()
        self.edges = self._build_edges()
        for edge in self.edges:
            edge.source.add_edge(edge)
            edge.target.add_edge(edge)

        # This is a hack to make sure that the LLM node is sent to
        # the toolkit node
        self._build_node_params()
        # remove invalid nodes
        self._remove_invalid_nodes()

    def _build_node_params(self) -> None:
        """Identifies and handles the LLM node within the graph."""
        llm_node = None
        for node in self.nodes:
            node._build_params()
            if isinstance(node, LLMNode):
                llm_node = node

        if llm_node:
            for node in self.nodes:
                if isinstance(node, ToolkitNode):
                    node.params["llm"] = llm_node

    def _remove_invalid_nodes(self) -> None:
        """Removes invalid nodes from the graph."""
        self.nodes = [
            node
            for node in self.nodes
            if self._validate_node(node)
            or (len(self.nodes) == 1 and len(self.edges) == 0)
        ]

    def _validate_node(self, node: Node) -> bool:
        """Validates a node."""
        # All nodes that do not have edges are invalid
        return len(node.edges) > 0

    def get_node(self, node_id: str) -> Union[None, Node]:
        """Returns a node by id."""
        return next((node for node in self.nodes if node.id == node_id), None)

    def get_nodes_with_target(self, node: Node) -> List[Node]:
        """Returns the nodes connected to a node."""
        connected_nodes: List[Node] = [
            edge.source for edge in self.edges if edge.target == node
        ]
        return connected_nodes

    def build(self) -> List[Node]:
        """Builds the graph."""
        # Get root node
        root_node = payload.get_root_node(self)
        if root_node is None:
            raise ValueError("No root node found")
        return root_node.build()

    def get_node_neighbors(self, node: Node) -> Dict[Node, int]:
        """Returns the neighbors of a node."""
        neighbors: Dict[Node, int] = {}
        for edge in self.edges:
            if edge.source == node:
                neighbor = edge.target
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
            elif edge.target == node:
                neighbor = edge.source
                if neighbor not in neighbors:
                    neighbors[neighbor] = 0
                neighbors[neighbor] += 1
        return neighbors

    def _build_edges(self) -> List[Edge]:
        """Builds the edges of the graph."""
        # Edge takes two nodes as arguments, so we need to build the nodes first
        # and then build the edges
        # if we can't find a node, we raise an error

        edges: List[Edge] = []
        for edge in self._edges:
            source = self.get_node(edge["source"])
            target = self.get_node(edge["target"])
            if source is None:
                raise ValueError(f"Source node {edge['source']} not found")
            if target is None:
                raise ValueError(f"Target node {edge['target']} not found")
            edges.append(Edge(source, target))
        return edges

    def _get_node_class(self, node_type: str, node_lc_type: str) -> Type[Node]:
        """Returns the node class based on the node type."""
        if node_type in FILE_TOOLS:
            return FileToolNode
        if node_type in NODE_TYPE_MAP:
            return NODE_TYPE_MAP[node_type]
        return NODE_TYPE_MAP[node_lc_type] if node_lc_type in NODE_TYPE_MAP else Node

    def _build_nodes(self) -> List[Node]:
        """Builds the nodes of the graph."""
        nodes: List[Node] = []
        for node in self._nodes:
            node_data = node["data"]
            node_type: str = node_data["type"]  # type: ignore
            node_lc_type: str = node_data["node"]["template"]["_type"]  # type: ignore

            NodeClass = self._get_node_class(node_type, node_lc_type)
            nodes.append(NodeClass(node))

        return nodes

    def get_children_by_node_type(self, node: Node, node_type: str) -> List[Node]:
        """Returns the children of a node based on the node type."""
        children = []
        node_types = [node.data["type"]]
        if "node" in node.data:
            node_types += node.data["node"]["base_classes"]
        if node_type in node_types:
            children.append(node)
        return children

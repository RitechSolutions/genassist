from typing import Dict, List, Any, Optional
from uuid import uuid4
from copy import deepcopy
from app.modules.workflow.manage.data_models import ValidationError
from app.schemas.dynamic_form_schemas.base import FieldSchema
from app.schemas.dynamic_form_schemas.nodes import NODE_DIALOG_SCHEMAS


#TODO: Validate Handlers
class WorkflowManager:
    def __init__(
        self,
        name: str,
        description: str,
        user_id: str,
        agent_id: str,
        workflow_id: Optional[str] = None
    ):
        self.workflow = {
            "id": workflow_id or str(uuid4()),
            "name": name,
            "description": description,
            "user_id": user_id,
            "agent_id": agent_id,
            "nodes": [],
            "edges": []
        }

    json_nodes = []
    json_edges = []
    # ------------------------
    # Core helpers
    # ------------------------
    def _find_node(self, node_id: str) -> Optional[Dict]:
        return next((n for n in self.workflow["nodes"] if n["id"] == node_id), None)

    def _node_name(self, node: Dict) -> str:
        return node.get("data", {}).get("name", node["id"])
    
    # define default values for different field types
    _DEFAULT_BY_TYPE = {
        "text": "",
        "select": None,
        "number": 0,
        "boolean": False,
    }

    def _build_data_fields(self, fields: list[FieldSchema]) -> dict:
        data = {}

        for field in fields:
            if field.default is not None:
                value = field.default
            else:
                value = self._DEFAULT_BY_TYPE.get(field.type)

            data[field.name] = value

        return data


    
    def _gen_node_from_type(self, node_type: str, name: str) -> Dict:
        fields = NODE_DIALOG_SCHEMAS.get(node_type) or []     
        node={
            "id": str(uuid4()),
            "type": node_type,
            "data": {
                **self._build_data_fields(fields),
                "handlers": self.build_handlers(node_type),
            },
            "position": {"x": 0, "y": 0}
        }
        node["data"]["name"] = name
        node["data"]["label"] = name

        return node

    # ------------------------
    # Node operations
    # ------------------------
    def add_node(self, node: Dict) -> None:
        if self._find_node(node["id"]):
            raise ValueError(f"Node {node['id']} already exists")
        self.workflow["nodes"].append(node)

    def update_node(self, node_id: str, updates: Dict) -> None:
        node = self._find_node(node_id)
        if not node:
            raise ValueError("Node not found")
        node.update(updates)

    def update_node_properties(self, node_id: str, data_updates: Dict) -> None:
        node = self._find_node(node_id)
        if not node:
            raise ValueError("Node not found")
        node.setdefault("data", {}).update(data_updates)

    def delete_node(self, node_id: str) -> None:
        self.workflow["nodes"] = [
            n for n in self.workflow["nodes"] if n["id"] != node_id
        ]
        self.workflow["edges"] = [
            e for e in self.workflow["edges"]
            if e["source"] != node_id and e["target"] != node_id
        ]

    def replace_node(self, node_id: str, new_node: Dict) -> None:
        old = self._find_node(node_id)
        if not old:
            raise ValueError("Node not found")

        new_node = deepcopy(new_node)
        new_node["id"] = node_id

        self.delete_node(node_id)
        self.workflow["nodes"].append(new_node)

    # ------------------------
    # Edge operations
    # ------------------------
    def add_edge(
        self,
        source: str,
        target: str,
        source_handle: str = "output",
        target_handle: str = "input"
    ) -> None:
        if not self._find_node(source) or not self._find_node(target):
            raise ValueError("Invalid source or target")

        self.workflow["edges"].append({
            "id": f"reactflow__edge-{source}{source_handle}-{target}{target_handle}",
            "source": source,
            "target": target,
            "sourceHandle": source_handle,
            "targetHandle": target_handle,
            "type": "default",
            "style": {
                "strokeWidth": 2,
                "stroke": "hsl(var(--brand-600))",
                "strokeDasharray": "7,7"
            },
            "markerEnd": {
                "type": "arrowclosed",
                "width": 16,
                "height": 16,
                "color": "hsl(var(--brand-600))"
            },
        })

    def add_edge_source_to_current(self, source_node_id: str, current_node_id: str):
        self.add_edge(source_node_id, current_node_id)

    def add_edge_current_to_successor(self, current_node_id: str, successor_node_id: str):
        self.add_edge(current_node_id, successor_node_id)

    # ------------------------
    # Validation
    # ------------------------
    def validate_node(self, node: Dict) -> List[ValidationError]:
        errors = []

        if "id" not in node:
            errors.append(ValidationError(
                node_id="unknown",
                node_name="unknown",
                field="id",
                error="Missing node id"
            ))

        data = node.get("data", {})
        if not data.get("name"):
            errors.append(ValidationError(
                node_id=node["id"],
                node_name=self._node_name(node),
                field="data.name",
                error="Node name is required"
            ))

        handlers = data.get("handlers", [])
        if not handlers:
            errors.append(ValidationError(
                node_id=node["id"],
                node_name=self._node_name(node),
                field="data.handlers",
                error="At least one handler is required"
            ))

        return errors

    def validate_workflow(self) -> List[ValidationError]:
        errors: List[ValidationError] = []

        node_ids = {n["id"] for n in self.workflow["nodes"]}

        # Node-level validation
        for node in self.workflow["nodes"]:
            errors.extend(self.validate_node(node))

        # Edge validation
        for edge in self.workflow["edges"]:
            if edge["source"] not in node_ids:
                errors.append(ValidationError(
                    node_id=edge["source"],
                    node_name="unknown",
                    field="edge.source",
                    error="Source node does not exist"
                ))

            if edge["target"] not in node_ids:
                errors.append(ValidationError(
                    node_id=edge["target"],
                    node_name="unknown",
                    field="edge.target",
                    error="Target node does not exist"
                ))

        return errors

    # ------------------------
    # Export
    # ------------------------
    def to_dict(self) -> Dict:
        return deepcopy(self.workflow)

    # ------------------------
    # Create Workflow from wizard
    # ------------------------

    def generate_from_wizard(self, wizard_json: Dict[str, Any]) -> None:
        # Example implementation - adapt based on actual wizard JSON structure
        steps = wizard_json.get("steps", [])
        previous_node_id = None

        for step in steps:
            node_id = str(uuid4())
            node = {
                "id": node_id,
                "type": step.get("type", "default"),
                "data": {
                    "name": step.get("name", f"Step {node_id}"),
                    "handlers": step.get("handlers", [])
                },
                "position": step.get("position", {"x": 0, "y": 0})
            }
            self.add_node(node)

            if previous_node_id:
                self.add_edge(previous_node_id, node_id)

            previous_node_id = node_id


    def generate_nodes_from_wizard(self, input_data: Dict) -> List[Dict]:
        output_nodes = []

        for index, node in enumerate(input_data["workflow"]):
            node_type = node["node_name"]
            name = node["node_name"]

            x = index * 500 + 50
            y = 150
            
            output_nodes.append({
                "id": str(uuid4()),
                "type": node_type,
                "width": 400,
                "height": 174 if node["node_name"] == "chatInputNode" else 226,
                "dragging": False,
                "selected": False,
                "position": {"x": x, "y": y},
                "positionAbsolute": {"x": x, "y": y},
                "data": {
                    "name": name,
                    "label": name,
                    "handlers": self.build_handlers(node["node_name"]),
                    **(
                        {
                            "inputSchema": {
                                "message": {
                                    "type": "string",
                                    "required": True,
                                    "description": "The input received from the user.",
                                    "defaultValue": ""
                                }
                            }
                        }
                        if node["node_name"] == "chatInputNode"
                        else {}
                    )
                }
            })
            self.json_nodes.append(output_nodes[-1])

        return output_nodes

    def generate_edges_from_wizard(self, input_data: Dict) -> List[Dict]:
        output_edges = []

        
        for index, node in enumerate(input_data["workflow"]):
            if index > 0:
                output_edges.append({
                    "id": f"reactflow__edge-{self.json_nodes[index - 1]['id']}output-{self.json_nodes[index]['id']}input",
                    "type": "default",
                    "style": {
                        "strokeWidth": 2,
                        "stroke": "hsl(var(--brand-600))",
                        "strokeDasharray": "7,7"
                    },
                    "source": self.json_nodes[index - 1]['id'],
                    "target": self.json_nodes[index]['id'],
                    "markerEnd": {
                        "type": "arrowclosed",
                        "width": 16,
                        "height": 16,
                        "color": "hsl(var(--brand-600))"
                    },
                    "sourceHandle": "output",
                    "targetHandle": "input"
                })
                self.json_edges.append(output_edges[-1])

        return output_edges
    

    def build_handlers(self, node_name: str) -> List[Dict]:
        if node_name == "chatInputNode":
            return [{
                "id": "output",
                "type": "source",
                "position": "right",
                "compatibility": "any"
            }]
        if node_name == "chatOutputNode":
            return [{
                "id": "input",
                "type": "target",
                "position": "left",
                "compatibility": "any"
            }]

        return [
            {
                "id": "input",
                "type": "target",
                "position": "left",
                "compatibility": "any"
            },
            {
                "id": "output",
                "type": "source",
                "position": "right",
                "compatibility": "any"
            }
        ]
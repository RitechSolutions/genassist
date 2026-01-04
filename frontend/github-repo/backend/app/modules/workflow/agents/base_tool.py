from typing import Callable, Protocol


def to_snake_case(not_snake_case):
    final = ''
    for i in range(len(not_snake_case)):
        item = not_snake_case[i]
        next_char_will_be_underscored = False
        if i < len(not_snake_case) - 1:
            next_char_will_be_underscored = (
                not_snake_case[i+1] == "_" or
                not_snake_case[i+1] == " " or
                not_snake_case[i+1].isupper()
            )
        if (item == " " or item == "_") and next_char_will_be_underscored:
            continue
        elif (item == " " or item == "_"):
            final += "_"
        elif item.isupper():
            final += "_"+item.lower()
        else:
            final += item
    if final and final[0] == "_":
        final = final[1:]
    return final

class Tool(Protocol):
    """Protocol for tools"""
    name: str
    description: str
    
    def invoke(self, **kwargs) -> str:
        """Execute the tool with given arguments"""
        ...

class BaseTool(Tool):
    """Base class for tools"""
    def __init__(self, node_id: str, name: str, description: str, parameters: dict, function: Callable, return_direct: bool = False):
        self.node_id = node_id
        self.name = to_snake_case(name)
        self.description = description
        filtered_params = {k: v for k, v in parameters.items() if "session." not in k}
        self.parameters = filtered_params
        self.function = function
        self.return_direct = return_direct

    def invoke(self, **kwargs) -> str:
        """Execute the tool with given arguments"""
        return self.function({"parameters": kwargs})

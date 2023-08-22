from typing import TYPE_CHECKING, Literal
from .value import *

if TYPE_CHECKING:
    from .base_node import BaseFuncNode


class Function:
    name: str
    params: list[tuple[str, Type]]
    return_type: Type
    specifier: Literal["call", "constexpr", "inline", "__asm"]
    node: "BaseFuncNode"

    def __init__(self, name: str, params: list[tuple[str, Type]], return_type: Type, specifier: Literal["call", "constexpr", "inline", "__asm"], node: "BaseFuncNode"):
        """
        Args:
            name: Name of the function.
            params: Parameters passed to the function.
            return_type: Return type of the function.
	        specifier: Specifier of the function
            node: Node which defines the function. Used for generating inline function calls.
        """

        self.name = name
        self.params = params
        self.return_type = return_type
        self.specifier = specifier
        self.node = node

    def __hash__(self):
        return hash((self.name, tuple(self.params), self.return_type))

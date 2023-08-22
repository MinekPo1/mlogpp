from contextvars import ContextVar
from functools import wraps
from typing import ClassVar

from .util import Position
from .instruction import Instruction, Instructions
from .value import NullValue, Value
from .scope import Scopes


class Node:
    """
    Base node class.
    """

    pos: Position
    _from_pos: ClassVar[ContextVar[Position]] = ContextVar("_from_pos")

    def __init__(self, pos: Position):
        self.pos = pos

    def __init_subclass__(cls) -> None:
        # metaprogramming: make _from_node point to the node currently being generated
        generate = cls.generate
        @wraps(cls.generate)
        def wrapper(self):
            token = Node._from_pos.set(self.pos)
            out = generate(self)
            Node._from_pos.reset(token)
            return out
        cls.generate = wrapper

    def get_pos(self) -> Position:
        """
        Get position of the node.

        Returns:
            Position of the node.
        """

        return self.pos

    def __str__(self):
        """
        Convert the node to a string, debug only.

        Returns:
            A string, similar to the unparsed mlog++ code.
        """

        return "NODE"

    def generate(self) -> Instruction | Instructions:
        """
        Generate the node.

        Returns:
            The generated code.
        """

        return Instructions()

    def get(self) -> tuple[Instruction | Instructions, Value]:
        """
        Get the node's value and code to obtain it.

        Returns:
            A tuple containing the code to obtain the value and the value.
        """

        return Instructions(), NullValue()

    def precalc(self) -> Value | None:
        """
        Attempt to precalculate the node's value.

        Returns:
            The value if succeeded, else None.
        """

        return None

class BaseFuncNode(Node):
    def generate_func(self, suffix: str = "") -> Instruction | Instructions:
        return Instructions()

class CodeBlockNode(Node):
    """
    Block of code.
    """

    code: list[Node]
    name: str | None

    def __init__(self, code: list[Node], name: str | None):
        super().__init__(Position(0, 0, 0, "", ""))

        self.code = code
        self.name = name

    def __str__(self):
        string = "{\n"
        for node in self.code:
            string += str(node) + "\n"
        return string + "}"

    def generate(self) -> Instruction | Instructions:
        ins = Instructions()

        for node in self.code:
            ins += node.generate()

        return ins
    
    def push_scope(self) -> None:
        """
        Push this node's scope to the scope stack.
        """

        Scopes.push(self.name)

    @staticmethod
    def pop_scope() -> None:
        """
        Pop this node's scope from the scope stack.
        """

        Scopes.pop()

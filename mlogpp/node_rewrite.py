import types

from .util import Position
from .instruction import *
from .value import *
from .generator import Gen
from .scope import Scope, Scopes
from .function import Function
from .error import Error
from . import constants


class Node:
    """
    base node class
    """

    pos: Position

    def __init__(self, pos: Position):
        self.pos = pos

    def get_pos(self) -> Position:
        return self.pos

    def __str__(self):
        return "NODE"

    def generate(self) -> Instruction | Instructions:
        return Instructions()

    def get(self) -> tuple[Instruction | Instructions, Value]:
        return Instructions(), NullValue()

    def scope_rename(self):
        pass


class CodeBlockNode(Node):
    """
    block of code
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

        Scopes.push(self.name)

        for node in self.code:
            ins += node.generate()

        Scopes.pop()

        return ins

    def scope_rename(self):
        for node in self.code:
            node.scope_rename()


class DeclarationNode(Node):
    """
    variable declaration node
    """

    var: VariableValue
    value: Node | None

    def __init__(self, pos: Position, var: VariableValue, value: Node | None):
        super().__init__(pos)

        self.var = var
        self.value = value

    def __str__(self):
        return f"{self.var.type.name} {self.var.name} = {str(self.value)}"

    def generate(self) -> Instruction | Instructions:
        if Scopes.get(self.var.name) is not None:
            Error.already_defined_var(self, self.var.name)

        Scopes.add(self.var)

        if self.value is not None:
            value_code, value = self.value.get()

            if value.type not in self.var.type:
                Error.incompatible_types(self, value.type, self.var.type)

            return value_code + MInstruction(MInstructionType.SET, [self.var, value])

        return Instructions()

    def scope_rename(self):
        self.var.name = Scopes.rename(self.var.name, True)
        if self.value is not None:
            self.value.scope_rename()


class AssignmentNode(Node):
    """
    variable assignment node
    """

    var: str
    op: str
    value: Node

    OPERATORS = {
        "+=": "add",
        "-=": "sub",
        "%=": "mod",
        "&=": "and",
        "|=": "or",
        "^=": "xor",
        "*=": "mul",
        "/=": "div",
        "**=": "pow",
        "//=": "idiv",
        "<<": "shl",
        ">>": "shr"
    }

    def __init__(self, pos: Position, var: str, op: str, value: Node):
        super().__init__(pos)

        self.var = var
        self.op = op
        self.value = value

    def __str__(self):
        return f"{self.var} {self.op} {self.value}"

    def generate(self) -> Instruction | Instructions:
        if isinstance(var := Scopes.get(self.var), VariableValue):
            if var.const:
                Error.write_to_const(self, self.var)

            value_code, value = self.value.get()

            if self.op == "=":
                if value.type not in var.type:
                    Error.incompatible_types(self, value.type, var.type)

                return value_code + MInstruction(MInstructionType.SET, [var, value])
            else:
                if var.type not in Type.NUM:
                    Error.incompatible_types(self, var.type, Type.NUM)
                if value.type not in Type.NUM:
                    Error.incompatible_types(self, value.type, Type.NUM)

                return value_code + MInstruction(MInstructionType.OP, [self.OPERATORS[self.op], var, var, value])

        if self.op == "=" and "." in self.var and (spl := self.var.split("."))[1] in constants.CONTROLLABLE:
            value_code, value = self.value.get()

            if value.type != Type.NUM:
                Error.incompatible_types(self, value.type, Type.NUM)

            if not isinstance(var := Scopes.get(spl[0]), VariableValue):
                Error.undefined_variable(self, spl[0])

            if var.type != Type.BLOCK:
                Error.incompatible_types(self, var.type, Type.BLOCK)

            return value_code + MInstruction(MInstructionType.CONTROL, [
                spl[1],
                var,
                value,
                "_", "_", "_"
            ])

        Error.undefined_variable(self, self.var)

    def scope_rename(self):
        self.var = Scopes.rename(self.var)
        self.value.scope_rename()


class IndexedAssignmentNode(AssignmentNode):
    """
    indexed variable assignment node
    """

    index: Node

    def __init__(self, pos: Position, var: str, index: Node, op: str, value: Node):
        super().__init__(pos, var, op, value)

        self.index = index

    def __str__(self):
        return f"{self.var}[{self.index}] {self.op} {self.value}"

    def generate(self) -> Instruction | Instructions:
        if (var := Scopes.get(self.var)) is not None:
            value_code, value = self.value.get()
            index_code, index = self.index.get()

            if var.type not in Type.NUM:
                Error.incompatible_types(self, var.type, Type.NUM)
            if value.type not in Type.NUM:
                Error.incompatible_types(self, value.type, Type.NUM)
            if index.type not in Type.NUM:
                Error.incompatible_types(self, index.type, Type.NUM)

            if self.op == "=":
                return value_code + index_code + MInstruction(MInstructionType.WRITE, [value, var, index])
            else:
                tmp = Gen.temp_var(Type.NUM)
                return index_code + MInstruction(MInstructionType.READ, [tmp, var, index]) + value_code + \
                       MInstruction(MInstructionType.OP, [AssignmentNode.OPERATORS[self.op], tmp, tmp, value]) + \
                       MInstruction(MInstructionType.WRITE, [tmp, var, index])

        Error.undefined_variable(self, self.var)

    def scope_rename(self):
        super().scope_rename()
        self.index.scope_rename()


class BinaryOpNode(Node):
    """
    binary operator node
    """

    left: Node
    right: list[tuple[str, Node]] | None

    OPERATORS = {
        "+": "add",
        "-": "sub",
        "*": "mul",
        "/": "div",
        "//": "idiv",
        "%": "mod",
        "**": "pow",
        "==": "equal",
        "!=": "notEqual",
        "&&": "land",
        "||": "or",
        "<": "lessThan",
        "<=": "lessThanEq",
        ">": "greaterThan",
        ">=": "greaterThanEq",
        "===": "strictEqual",
        "<<": "shl",
        ">>": "shr",
        "|": "or",
        "&": "and",
        "^": "xor"
    }

    EQUALITY = {
        "==",
        "!=",
        "==="
    }

    def __init__(self, pos: Position, left: Node, right: list[tuple[str, Node]] | None):
        super().__init__(pos)

        self.left = left
        self.right = right

    def __str__(self):
        string = str(self.left)
        for op, node in self.right:
            string += " " + op + f" {str(node)}"
        return string

    def get(self) -> tuple[Instruction | Instructions, Value]:
        code, value = self.left.get()

        if value.type not in Type.NUM and len(self.right) > 0:
            for op, _ in self.right:
                if op not in BinaryOpNode.EQUALITY:
                    Error.incompatible_types(self, value.type, Type.NUM)

        if self.right is not None and len(self.right) > 0:
            tmpv = Gen.temp_var(Type.NUM)
            if tmpv != value:
                code += MInstruction(MInstructionType.SET, [tmpv, value])

            for op, node in self.right:
                value_code, value = node.get()

                if value.type not in Type.NUM:
                    Error.incompatible_types(self, value.type, Type.NUM)

                code += value_code + MInstruction(MInstructionType.OP, [BinaryOpNode.OPERATORS[op], tmpv, tmpv, value])

            return code, tmpv

        return code, value

    def scope_rename(self):
        self.left.scope_rename()
        for _, node in self.right:
            node.scope_rename()


class UnaryOpNode(Node):
    """
    unary operator node
    """

    op: str
    value: Node

    def __init__(self, pos: Position, op: str, value: Node):
        super().__init__(pos)

        self.op = op
        self.value = value

    def __str__(self):
        return f"{self.op}{str(self.value)}"

    def get(self) -> tuple[Instruction | Instructions, Value]:
        code, value = self.value.get()

        if value.type not in Type.NUM:
            Error.incompatible_types(self, value.type, Type.NUM)

        tmpv = Gen.temp_var(Type.NUM)

        match self.op:
            case "-":
                code += MInstruction(MInstructionType.OP, ["sub", tmpv, 0, tmpv])
            case "!":
                code += MInstruction(MInstructionType.OP, ["notEqual", tmpv, tmpv, "true"])
            case "~":
                code += MInstruction(MInstructionType.OP, ["not", tmpv, tmpv, "_"])

        return code, value

    def scope_rename(self):
        self.value.scope_rename()


class CallNode(Node):
    """
    function call node
    """

    name: str
    params: list[Node]

    return_value: Value

    def __init__(self, pos: Position, name: str, params: list[Node]):
        super().__init__(pos)

        self.name = name
        self.params = params

        self.return_value = NullValue()

    def generate(self) -> Instruction | Instructions:
        code = Instructions()

        if not isinstance(fun := Scopes.get(self.name), Function):
            Error.undefined_function(self, self.name)

        if len(self.params) != len(fun.params):
            Error.invalid_arg_count(self, len(self.params), len(fun.params))

        if fun.return_type != Type.NULL:
            self.return_value = VariableValue(fun.return_type, f"__f_{self.name}_retv")

        for i, param in enumerate(self.params):
            param_code, param_value = param.get()

            if param_value.type != fun.params[i][1]:
                Error.incompatible_types(self, param_value.type, fun.params[i][1])

            code += param_code
            code += MInstruction(MInstructionType.SET, [
                VariableValue(fun.params[i][1], Scope(self.name).rename(fun.params[i][0])),
                param_value
            ])

        code += MInstruction(MInstructionType.OP, [
            "add",
            VariableValue(Type.NUM, f"__f_{self.name}_ret"),
            VariableValue(Type.NUM, "@counter"),
            NumberValue(1)
        ])
        code += MppInstructionJump(f"__f_{self.name}")

        return code

    def get(self) -> tuple[Instruction | Instructions, Value]:
        return self.generate(), self.return_value

    def scope_rename(self):
        for param in self.params:
            param.scope_rename()


class Param(enum.Enum):
    INPUT = enum.auto()
    OUTPUT = enum.auto()
    CONFIG = enum.auto()
    UNUSED = enum.auto()


class NativeCallNode(Node):
    """
    native function call node
    """

    name: str
    params: list[Node | str]

    return_value: Value

    NATIVES = {
        "read": (
            (Param.OUTPUT, Type.NUM),
            (Param.INPUT, Type.BLOCK),
            (Param.INPUT, Type.NUM)
        ),

        "write": (
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.BLOCK),
            (Param.INPUT, Type.NUM)
        ),

        "draw.clear": (
            (Param.INPUT, Type.NUM),
        ) * 3,
        "draw.color": (
            (Param.INPUT, Type.NUM),
        ) * 4,
        "draw.col": (
            (Param.INPUT, Type.NUM),
        ),
        "draw.stroke": (
            (Param.INPUT, Type.NUM),
        ),
        "draw.line": (
            (Param.INPUT, Type.NUM),
        ) * 4,
        "draw.rect": (
            (Param.INPUT, Type.NUM),
        ) * 4,
        "draw.lineRect": (
            (Param.INPUT, Type.NUM),
        ) * 4,
        "draw.poly": (
            (Param.INPUT, Type.NUM),
        ) * 5,
        "draw.linePoly": (
            (Param.INPUT, Type.NUM),
        ) * 5,
        "draw.triangle": (
            (Param.INPUT, Type.NUM),
        ) * 5,
        "draw.image": (
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.ITEM_TYPE),
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.NUM)
        ),

        "print": (
            (Param.INPUT, Type.ANY),
        ),

        "drawflush": (
            (Param.INPUT, Type.BLOCK),
        ),

        "printflush": (
            (Param.INPUT, Type.BLOCK),
        ),

        "getlink": (
            (Param.OUTPUT, Type.BLOCK),
            (Param.INPUT, Type.NUM)
        ),

        "control.enabled": (
            (Param.INPUT, Type.BLOCK),
            (Param.INPUT, Type.NUM)
        ),
        "control.shoot": (
            (Param.INPUT, Type.BLOCK),
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.NUM)
        ),
        "control.shootp": (
            (Param.INPUT, Type.BLOCK),
            (Param.INPUT, Type.UNIT),
            (Param.INPUT, Type.NUM)
        ),
        "control.config": (
            (Param.INPUT, Type.BLOCK),
            (Param.INPUT, Type.NUM)
        ),
        "control.color": (
            (Param.INPUT, Type.BLOCK),
            (Param.INPUT, Type.NUM)
        ),

        "radar": (
            (Param.CONFIG, ("any", "enemy", "ally", "player", "attacker", "flying", "boss", "ground")),
            (Param.CONFIG, ("any", "enemy", "ally", "player", "attacker", "flying", "boss", "ground")),
            (Param.CONFIG, ("any", "enemy", "ally", "player", "attacker", "flying", "boss", "ground")),
            (Param.CONFIG, ("distance", "health", "shield", "armor", "maxHealth")),
            (Param.INPUT, Type.BLOCK),
            (Param.INPUT, Type.NUM),
            (Param.OUTPUT, Type.UNIT)
        )
    } | \
              {
                    f"sensor.{property}": (
                        (Param.OUTPUT, type_),
                        (Param.INPUT, Type.BLOCK | Type.UNIT)
                    ) for property, type_ in constants.SENSOR_READABLE.items()
    } | \
              {
        "wait": (
            (Param.INPUT, Type.NUM),
        ),

        "lookup.block": (
            (Param.OUTPUT, Type.BLOCK_TYPE),
            (Param.INPUT, Type.NUM)
        ),
        "lookup.unit": (
            (Param.OUTPUT, Type.UNIT_TYPE),
            (Param.INPUT, Type.NUM)
        ),
        "lookup.item": (
            (Param.OUTPUT, Type.ITEM_TYPE),
            (Param.INPUT, Type.NUM)
        ),
        "lookup.liquid": (
            (Param.OUTPUT, Type.LIQUID_TYPE),
            (Param.INPUT, Type.NUM)
        ),

        "packcolor": (
            (Param.OUTPUT, Type.NUM),
        ) + (
            (Param.INPUT, Type.NUM),
        ) * 4,

        "ubind": (
            (Param.INPUT, Type.UNIT_TYPE),
        ),

        "ucontrol.idle": tuple(),
        "ucontrol.stop": tuple(),
        "ucontrol.move": (
            (Param.INPUT, Type.NUM),
        ) * 2,
        "ucontrol.approach": (
            (Param.INPUT, Type.NUM),
        ) * 3,
        "ucontrol.boost": (
            (Param.INPUT, Type.NUM),
        ),
        "ucontrol.target": (
            (Param.INPUT, Type.NUM),
        ) * 3,
        "ucontrol.targetp": (
            (Param.INPUT, Type.UNIT),
            (Param.INPUT, Type.NUM),
        ),
        "ucontrol.itemDrop": (
            (Param.INPUT, Type.BLOCK),
            (Param.INPUT, Type.NUM),
        ),
        "ucontrol.itemTake": (
            (Param.INPUT, Type.BLOCK),
            (Param.INPUT, Type.ITEM_TYPE),
            (Param.INPUT, Type.NUM)
        ),
        "ucontrol.payDrop": tuple(),
        "ucontrol.payTake": (
            (Param.INPUT, Type.NUM),
        ),
        "ucontrol.payEnter": tuple(),
        "ucontrol.mine": (
            (Param.INPUT, Type.NUM),
        ) * 2,
        "ucontrol.flag": (
            (Param.INPUT, Type.NUM),
        ),
        "ucontrol.build": (
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.BLOCK_TYPE),
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.NUM)
        ),
        "ucontrol.getBlock": (
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.NUM),
            (Param.OUTPUT, Type.BLOCK_TYPE),
            (Param.OUTPUT, Type.BLOCK),
        ),
        "ucontrol.within": (
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.NUM),
            (Param.INPUT, Type.NUM),
            (Param.OUTPUT, Type.NUM)
        ),
        "ucontrol.unbind": tuple(),

        "uradar": (
            (Param.CONFIG, ("any", "enemy", "ally", "player", "attacker", "flying", "boss", "ground")),
            (Param.CONFIG, ("any", "enemy", "ally", "player", "attacker", "flying", "boss", "ground")),
            (Param.CONFIG, ("any", "enemy", "ally", "player", "attacker", "flying", "boss", "ground")),
            (Param.CONFIG, ("distance", "health", "shield", "armor", "maxHealth")),
            (Param.UNUSED, Type.ANY),
            (Param.INPUT, Type.NUM),
            (Param.OUTPUT, Type.UNIT)
        ),

        "ulocate.ore": (
            (Param.UNUSED, Type.ANY),
            (Param.UNUSED, Type.ANY),
            (Param.INPUT, Type.BLOCK_TYPE),
            (Param.OUTPUT, Type.NUM),
            (Param.OUTPUT, Type.NUM),
            (Param.OUTPUT, Type.NUM),
            (Param.UNUSED, Type.ANY)
        ),
        "ulocate.building": (
            (Param.CONFIG, ("core", "storage", "generator", "turret", "factory", "repair", "battery", "reactor")),
            (Param.INPUT, Type.NUM),
            (Param.UNUSED, Type.ANY),
            (Param.OUTPUT, Type.NUM),
            (Param.OUTPUT, Type.NUM),
            (Param.OUTPUT, Type.NUM),
            (Param.OUTPUT, Type.BLOCK)
        ),
        "ulocate.spawn": (
            (Param.UNUSED, Type.ANY),
            (Param.UNUSED, Type.ANY),
            (Param.UNUSED, Type.ANY),
            (Param.OUTPUT, Type.NUM),
            (Param.OUTPUT, Type.NUM),
            (Param.OUTPUT, Type.NUM),
            (Param.OUTPUT, Type.BLOCK)
        ),
        "ulocate.damaged": (
            (Param.UNUSED, Type.ANY),
            (Param.UNUSED, Type.ANY),
            (Param.UNUSED, Type.ANY),
            (Param.OUTPUT, Type.NUM),
            (Param.OUTPUT, Type.NUM),
            (Param.OUTPUT, Type.NUM),
            (Param.OUTPUT, Type.BLOCK)
        )
    }

    NATIVES_RETURN_POS = {
        "read": 0,
        "getlink": 0,
        "radar": 6
    } | \
                         {
        f"sensor.{property}": 0 for property in constants.SENSOR_READABLE.keys()
    } | \
                         {
        "lookup.block": 0,
        "lookup.unit": 0,
        "lookup.item": 0,
        "lookup.liquid": 0,
        "packcolor": 0,
        "ucontrol.within": 3,
        "uradar": 6
    }

    BUILTINS = {
        "max": 2,
        "min": 2,
        "abs": 1,
        "log": 1,
        "log10": 1,
        "ceil": 1,
        "floor": 1,
        "sqrt": 1,
        "sin": 1,
        "cos": 1,
        "tan": 1,
        "asin": 1,
        "acos": 1,
        "atan": 1,
        "len": 2,
        "rand": 1
    }

    def __init__(self, pos: Position, name: str, params: list[Node | str]):
        super().__init__(pos)

        self.name = name
        self.params = params

        self.return_value = NullValue()

    def __str__(self):
        return f"{self.name}({', '.join(map(str, self.params))})"

    def generate(self) -> Instruction | Instructions:
        if self.name in NativeCallNode.NATIVES:
            return self.generate_native()
        elif self.name in NativeCallNode.BUILTINS:
            return self.generate_builtin()

        Error.undefined_function(self, self.name)

    def generate_native(self) -> Instruction | Instructions:
        if (nat := NativeCallNode.NATIVES.get(self.name)) is None:
            Error.undefined_function(self, self.name)

        if len(self.params) != len(nat):
            Error.invalid_arg_count(self, len(self.params), len(nat))

        code = Instructions()

        params = []

        for i, param in enumerate(self.params):
            match nat[i][0]:
                case Param.CONFIG:
                    if isinstance(param, str):
                        params.append(param)
                case Param.UNUSED:
                    params.append("_")
                case Param.INPUT:
                    param_code, param_value = param.get()
                    if param_value.type not in nat[i][1]:
                        Error.incompatible_types(self, param_value.type, nat[i][1])
                    code += param_code
                    params.append(param_value)
                case Param.OUTPUT:
                    if i == NativeCallNode.NATIVES_RETURN_POS.get(self.name):
                        value = Gen.temp_var(nat[i][1])
                        self.return_value = value
                        params.append(value)
                    else:
                        if (var := Scopes.get(param)) is None:
                            var = VariableValue(nat[i][1], param)
                            Scopes.add(var)
                        elif isinstance(var, Function):
                            Error.already_defined_var(self, param)
                        elif var.type != nat[i][1]:
                            Error.incompatible_types(self, var.type, nat[i][1])
                        params.append(var)

        if "." in self.name:
            if self.name == "sensor":
                params.append("@" + self.name.split(".")[1])
            else:
                params = [self.name.split(".")[1]] + params

        code += MInstruction(MInstructionType[self.name.split(".")[0].upper()], params)

        return code

    def generate_builtin(self) -> Instruction | Instructions:
        if (nat := NativeCallNode.BUILTINS.get(self.name)) is None:
            Error.undefined_function(self, self.name)

        if len(self.params) != nat:
            Error.invalid_arg_count(self, len(self.params), nat)

        code = Instructions()

        params = []

        for param in self.params:
            param_code, param_value = param.get()
            if param_value.type != Type.NUM:
                Error.incompatible_types(self, param_value.type, Type.NUM)

            code += param_code
            params.append(param_value)

        out = Gen.temp_var(Type.NUM)

        code += MInstruction(MInstructionType.OP, [
            self.name,
            out,
            *params
        ] + ["_"] * (2 - len(params)))

        self.return_value = out

        return code

    def get(self) -> tuple[Instruction | Instructions, Value]:
        return self.generate(), self.return_value

    def scope_rename(self):
        for param in self.params:
            if isinstance(param, str):
                continue

            param.scope_rename()


class ValueNode(Node):
    """
    value node
    """

    def __init__(self, pos: Position, value):
        super().__init__(pos)

        self.value = value

    def __str__(self):
        return str(self.value)


class StringValueNode(ValueNode):
    """
    string value node
    """

    value: str

    def __init__(self, pos: Position, value: str):
        super().__init__(pos, value)

    def get(self) -> tuple[Instruction | Instructions, Value]:
        return Instructions(), StringValue(self.value)


class NumberValueNode(ValueNode):
    """
    number value node
    """

    value: int | float

    def __init__(self, pos: Position, value: int | float):
        super().__init__(pos, value)

    def get(self) -> tuple[Instruction | Instructions, Value]:
        return Instructions(), NumberValue(self.value)


class ContentValueNode(ValueNode):
    """
    content value node
    """

    value: str
    type: Type

    def __init__(self, pos: Position, value: str, type_: Type):
        super().__init__(pos, value)

        self.type = type_

    def get(self) -> tuple[Instruction | Instructions, Value]:
        return Instructions(), VariableValue(self.type, self.value)


class BlockValueNode(ValueNode):
    """
    linker block value node
    """

    value: str

    def __init__(self, pos: Position, value: str):
        super().__init__(pos, value)

    def get(self) -> tuple[Instruction | Instructions, Value]:
        return Instructions(), BlockValue(self.value)


class VariableValueNode(ValueNode):
    """
    variable value node
    """

    value: str

    def __init__(self, pos: Position, value: str):
        super().__init__(pos, value)

    def get(self) -> tuple[Instruction | Instructions, Value]:
        if isinstance(var := Scopes.get(self.value), VariableValue):
            return Instructions(), var

        if "." in self.value and (spl := self.value.split("."))[1] in constants.SENSOR_READABLE:
            if isinstance(var := Scopes.get(spl[0]), VariableValue):
                if var.type not in Type.BLOCK | Type.UNIT:
                    Error.incompatible_types(self, var.type, Type.BLOCK)

                out = Gen.temp_var(constants.SENSOR_READABLE[spl[1]])

                return Instructions() + MInstruction(MInstructionType.SENSOR, [out, var, "@" + spl[1]]), out

        Error.undefined_variable(self, self.value)   # TODO: being called incorrectly

    def scope_rename(self):
        self.value = Scopes.rename(self.value)


class IndexedValueNode(ValueNode):
    """
    indexed variable value node
    """

    value: str
    index: Node

    def __init__(self, pos: Position, value: str, index: Node):
        super().__init__(pos, value)

        self.index = index

    def __str__(self):
        return f"{self.value}[{self.index}]"

    def scope_rename(self):
        self.value = Scopes.rename(self.value)
        self.index.scope_rename()


class ReturnNode(Node):
    """
    return from function node
    """

    func: str
    value: Node | None

    def __init__(self, pos: Position, func: str, value: Node | None):
        super().__init__(pos)

        self.func = func
        self.value = value

    def generate(self) -> Instruction | Instructions:
        if self.value is None:
            return Instructions()

        value_code, value = self.value.get()

        if not isinstance(fun := Scopes.get(self.func), Function):
            Error.undefined_function(self, self.name)

        if value.type != fun.return_type:
            Error.incompatible_types(self, value.type, fun.return_type)

        return value_code + MInstruction(MInstructionType.SET, [
            VariableValue(value.type, f"__f_{self.func}_retv"),
            value
        ])

    def scope_rename(self):
        if self.value is not None:
            self.value.scope_rename()


class BreakNode(Node):
    """
    break loop node
    """

    loop: str

    def __init__(self, pos: Position, loop: str):
        super().__init__(pos)

        self.loop = loop


class ContinueNode(Node):
    """
    continue loop node
    """

    loop: str

    def __init__(self, pos: Position, loop: str):
        super().__init__(pos)

        self.loop = loop


class EndNode(Node):
    """
    end program node
    """

    def __init__(self, pos: Position):
        super().__init__(pos)


class IfNode(Node):
    """
    if conditional node
    """

    cond: Node
    code: CodeBlockNode
    else_code: CodeBlockNode | None

    def __init__(self, pos: Position, cond: Node, code: CodeBlockNode, else_code: CodeBlockNode | None):
        super().__init__(pos)

        self.cond = cond
        self.code = code
        self.else_code = else_code

    def scope_rename(self):
        self.cond.scope_rename()
        self.code.scope_rename()
        if self.else_code is not None:
            self.else_code.scope_rename()


class LoopNode(Node):
    """
    loop node
    """

    def __init__(self, pos: Position):
        super().__init__(pos)


class WhileNode(LoopNode):
    """
    while loop node
    """

    name: str
    cond: Node
    code: CodeBlockNode

    def __init__(self, pos: Position, name: str, cond: Node, code: CodeBlockNode):
        super().__init__(pos)

        self.name = name
        self.cond = cond
        self.code = code

    def scope_rename(self):
        self.code.scope_rename()
        self.code.scope_rename()


class ForNode(LoopNode):
    """
    for loop node
    """

    name: str
    init: Node
    cond: Node
    action: Node
    code: CodeBlockNode

    def __init__(self, pos: Position, name: str, init: Node, cond: Node, action: Node, code: CodeBlockNode):
        super().__init__(pos)

        self.name = name
        self.init = init
        self.cond = cond
        self.action = action
        self.code = code

    def scope_rename(self):
        self.init.scope_rename()
        self.cond.scope_rename()
        self.action.scope_rename()
        self.code.scope_rename()


class RangeNode(LoopNode):
    """
    range loop node
    """

    name: str
    var: str
    until: Node
    code: CodeBlockNode

    def __init__(self, pos: Position, name: str, var: str, until: Node, code: CodeBlockNode):
        super().__init__(pos)

        self.name = name
        self.var = var
        self.until = until
        self.code = code

    def generate(self) -> Instruction | Instructions:
        if (var := Scopes.get(self.var)) is None:
            var = VariableValue(Type.NUM, self.var)
            Scopes.add(var)
        elif isinstance(var, Function):
            Error.already_defined_var(self, self.var)
        elif var.type != Type.NUM:
            Error.incompatible_types(self, var.type, Type.NUM)

        until_code, until = self.until.get()

        if until.type != Type.NUM:
            Error.incompatible_types(self, until.type, Type.NUM)

        code = MInstruction(MInstructionType.SET, [var, NumberValue(0)]) + MppInstructionLabel(f"{self.name}_s") + \
               until_code + MppInstructionOJump(f"{self.name}_e", var, "greaterThanEq", until) + \
               self.code.generate() + MInstruction(MInstructionType.OP, ["add", var, var, NumberValue(1)]) + \
               MppInstructionJump(f"{self.name}_s") + MppInstructionLabel(f"{self.name}_e")

        return code

    def scope_rename(self):
        self.var = Scopes.rename(self.var, True)
        self.until.scope_rename()
        self.code.scope_rename()


class FunctionNode(Node):
    """
    function definition node
    """

    name: str
    params: list[tuple[str, Type]]
    return_type: Type
    code: CodeBlockNode

    def __init__(self, pos: Position, name: str, params: list[tuple[str, Type]], return_type: Type, code: CodeBlockNode):
        super().__init__(pos)

        self.name = name
        self.params = params
        self.return_type = return_type
        self.code = code

    def __str__(self):
        return f"function {self.name} ({', '.join(map(lambda t: t[1].name + ' ' + t[0], self.params))}) {self.code}"

    def generate(self) -> Instruction | Instructions:
        Scopes.add(Function(self.name, self.params, self.return_type))

        code = Instructions()

        code += MppInstructionJump(f"__f_{self.name}_end")
        code += MppInstructionLabel(f"__f_{self.name}")

        Scopes.push(self.name)
        for name, type_ in self.params:
            Scopes.add(VariableValue(type_, Scopes.rename(name, True)))

        self.code.scope_rename()
        code += self.code.generate()

        Scopes.pop()

        code += MInstruction(MInstructionType.SET, [
            VariableValue(Type.NUM, "@counter"),
            VariableValue(Type.NUM, f"__f_{self.name}_ret")
        ])
        code += MppInstructionLabel(f"__f_{self.name}_end")

        return code

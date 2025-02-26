import ast
import operator

from ..tokens import TokenType, Token
from ..generic_parser import GenericParser
from .node import *


class DeferredMathValue(Value):
    pass


class AsmParser(GenericParser):
    """
    Parse mlog++ assembly code.
    """

    def _init(self):
        # convert keyword and builtin tokens into id tokens
        for tok in self.tokens:
            if tok.type in (TokenType.KEYWORD, TokenType.NATIVE):
                tok.type = TokenType.ID

        self.const_expressions = True

    def parse_CodeBlock(self, name: str | None, end_at_rbrace: bool = True) -> CodeBlockNode:
        """
        Parse a block of code.

        Args:
            name: Name of the code block.
            end_at_rbrace: Break at a right bracket.

        Returns:
            The parsed block of code.
        """

        code = []
        while self.has_token():
            if self.lookahead_token(TokenType.RBRACE) and end_at_rbrace:
                self.next_token()
                break

            s = self.parse_Statement()
            if s is not None:
                code.append(s)

        return CodeBlockNode(code, name)

    def parse_Statement(self) -> Node | None:
        n = self.next_token()

        if n.type == TokenType.ID:
            if self.lookahead_token(TokenType.SET, "=") and self.lookahead_token(TokenType.COLON, n = 2):
                self.next_token(TokenType.SET, "=")
                self.next_token(TokenType.COLON)
                macro = ""
                
                while n.pos.line == self.lookahead_line():
                    macro += self.next_token().value
                
                return MacroNode(n.pos, n.value, macro)
                
            elif self.lookahead_token(TokenType.SET):
                op = self.next_token(TokenType.SET)
                if op.value == "=":
                    if self.lookahead_token(TokenType.ID) and self.lookahead_token(TokenType.LBRACK, None, 2):
                        cell = self.next_token(TokenType.ID)
                        self.next_token(TokenType.LBRACK)
                        index = self.parse_Value()
                        self.next_token(TokenType.RBRACK)
                        return CellReadNode(n.pos + op.pos, cell.value, index, n.value)

                    self.prev_token(2)
                    return self.parse_Operation()
                else:
                    return AssignmentNode(n.pos + op.pos, n.value, op.value, self.parse_Value())

            elif self.lookahead_token(TokenType.LPAREN) and n.value in MInstructionType.INSTRUCTION_NAMES:
                self.prev_token(1)
                return self.parse_Call()

            elif self.lookahead_token(TokenType.COLON):
                self.next_token(TokenType.COLON)
                return LabelNode(n.pos, n.value)

            elif self.lookahead_token(TokenType.LBRACK):
                self.next_token(TokenType.LBRACK)
                index = self.parse_Value()
                self.next_token(TokenType.RBRACK)
                op = self.next_token(TokenType.SET, "=")
                return CellWriteNode(n.pos + op.pos, n.value, index, self.parse_Value())

        elif n.type == TokenType.COLON:
            if self.lookahead_token(TokenType.ID):
                label = self.next_token(TokenType.ID)
                if self.lookahead_token(TokenType.LPAREN):
                    self.next_token(TokenType.LPAREN)
                    a = self.parse_Value()
                    op = self.next_token(TokenType.OPERATOR)
                    b = self.parse_Value()
                    self.next_token(TokenType.RPAREN)
                    return JumpNode(n.pos, label.value, (op.value, a, b))
                else:
                    return JumpNode(n.pos + label.pos, label.value, ("always", NullValue(), NullValue()))

        elif n.type in (TokenType.NUMBER, TokenType.STRING) and self.lookahead_line() != n.pos.line:
            return None

        Error.unexpected_token(n)

    def parse_Value(self) -> Value:
        n = self.next_token(TokenType.ID | TokenType.NUMBER | TokenType.STRING)
        if n.type == TokenType.ID:
            return VariableValue(Type.ANY, n.value)
        elif n.type == TokenType.NUMBER:
            try:
                return NumberValue(int(n.value))
            except ValueError:
                return NumberValue(float(n.value))
        elif n.type == TokenType.STRING:
            return StringValue(n.value)

        raise RuntimeError("Internal error")

    def parse_Operation(self) -> Node:
        var = self.next_token(TokenType.ID)
        self.next_token(TokenType.SET, "=")

        if self.lookahead_token(TokenType.OPERATOR):
            op = self.next_token(TokenType.OPERATOR).value
            a = self.parse_Value()

            return UnaryOpNode(var.pos, var.value, op, a)

        a = self.parse_Value()

        if self.lookahead_token(TokenType.OPERATOR):
            op = self.next_token(TokenType.OPERATOR).value
            b = self.parse_Value()

            return BinaryOpNode(var.pos, var.value, a, op, b)

        else:
            return AssignmentNode(var.pos, var.value, "=", a)

    def parse_Call(self) -> Node:
        name = self.next_token(TokenType.ID)
        self.next_token(TokenType.LPAREN)

        values = []
        last_tok = TokenType.LPAREN
        while self.has_token():
            tok = self.next_token()

            if tok.type == TokenType.RPAREN:
                if last_tok == TokenType.COMMA:
                    Error.unexpected_token(tok)

                break

            elif tok.type == TokenType.COMMA:
                if last_tok != TokenType.ID:
                    Error.unexpected_token(tok)

                last_tok = TokenType.COMMA

            else:
                if last_tok == TokenType.ID:
                    Error.unexpected_token(tok)

                last_tok = TokenType.ID
                self.prev_token()

                values.append(self.parse_Value())

        return CallNode(name.pos, name.value, values)

import ast
from collections.abc import Mapping

from asagent.core.tool_definition import ToolDefinition


class CalculatorTool:
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="builtin.calculator",
            display_name="Calculator",
            description="Evaluates a basic arithmetic expression.",
            input_schema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "An arithmetic expression using +, -, *, /, and parentheses.",
                    },
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        expression = arguments["expression"]
        if not isinstance(expression, str):
            raise ValueError("expression must be a string")

        try:
            parsed = ast.parse(expression, mode="eval")
        except SyntaxError as error:
            raise ValueError("expression is invalid") from error

        return str(self._evaluate(parsed.body))

    def _evaluate(self, node: ast.expr) -> int | float:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, int | float):
                raise ValueError("expression contains an unsupported value")
            return node.value

        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate(node.operand)
            if isinstance(node.op, ast.UAdd):
                return operand
            if isinstance(node.op, ast.USub):
                return -operand

        if isinstance(node, ast.BinOp):
            left = self._evaluate(node.left)
            right = self._evaluate(node.right)

            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right

        raise ValueError("expression contains unsupported syntax")

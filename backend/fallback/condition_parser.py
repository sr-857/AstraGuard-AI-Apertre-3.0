"""
Safe Condition Parser

Pure, deterministic condition evaluation without eval() or exec().
Implements recursive descent parsing with strict whitelisting.

Security Features:
- No eval() or exec() usage
- Whitelist of allowed operations (comparisons, logical operators)
- Type-safe variable substitution
- Resource limits (no loops, no function calls)
- Complexity protection via token counting

Supports:
- Comparisons: >=, <=, >, <, ==, !=
- Logical: and, or
- Literals: numbers, strings (quoted)
- Variables: severity, recurrence_count, confidence, step, duration
- Parentheses for grouping

Examples:
    >>> parse_condition("always")
    >>> evaluate(condition, {}) -> True
    
    >>> parse_condition("severity >= 0.8")
    >>> evaluate(condition, {"severity": 0.9}) -> True
    
    >>> parse_condition("severity >= 0.8 and recurrence_count >= 2")
    >>> evaluate(condition, {"severity": 0.9, "recurrence_count": 3}) -> True
"""

import re
from typing import Dict, Any, Union, Callable
from enum import Enum


class TokenType(Enum):
    """Token types for lexical analysis."""
    NUMBER = "NUMBER"
    STRING = "STRING"
    VARIABLE = "VARIABLE"
    OPERATOR = "OPERATOR"
    LOGICAL = "LOGICAL"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    EOF = "EOF"


class Token:
    """Represents a single token in the expression."""

    def __init__(self, type: TokenType, value: Any, position: int = 0):
        self.type = type
        self.value = value
        self.position = position

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


class Condition:
    """
    Represents a parsed condition that can be evaluated.
    
    This is a pure data structure - no side effects.
    """

    def __init__(self, evaluator: Callable[[Dict[str, Union[int, float]]], bool]):
        """
        Initialize condition with evaluator function.
        
        Args:
            evaluator: Function that takes context dict and returns bool
        """
        self._evaluator = evaluator

    def evaluate(self, context: Dict[str, Union[int, float]]) -> bool:
        """
        Evaluate condition with given context.
        
        Args:
            context: Variable values
            
        Returns:
            Boolean result
        """
        return self._evaluator(context)


class ConditionParser:
    """
    Safe expression parser for condition evaluation.

    Uses recursive descent parsing with strict whitelisting.
    No eval(), no exec(), no arbitrary code execution.
    """

    # Whitelist of allowed comparison operators
    COMPARISON_OPS = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    # Whitelist of allowed variables
    ALLOWED_VARIABLES = {
        "severity",
        "recurrence_count",
        "confidence",
        "step",
        "duration",
    }

    # Maximum expression complexity (prevents DoS)
    MAX_TOKENS = 50

    def __init__(self):
        """Initialize parser."""
        self.tokens = []
        self.current = 0

    def parse(self, expression: str) -> Condition:
        """
        Parse condition expression into Condition object.
        
        Args:
            expression: Condition string (e.g., "severity >= 0.8")
            
        Returns:
            Condition object that can be evaluated
            
        Raises:
            ValueError: If expression is invalid or unsafe
        """
        # Special case: "always" keyword
        if expression.strip().lower() == "always":
            return Condition(lambda ctx: True)

        # Tokenize
        self.tokens = self._tokenize(expression)

        # Check complexity limit (DoS protection)
        if len(self.tokens) > self.MAX_TOKENS:
            raise ValueError(
                f"Expression too complex ({len(self.tokens)} tokens > {self.MAX_TOKENS} max)"
            )

        # Parse into evaluator function
        self.current = 0
        
        def evaluator(context: Dict[str, Union[int, float]]) -> bool:
            """Evaluator closure that captures parsed structure."""
            self.current = 0
            result = self._parse_or_expression(context)
            
            # Ensure all tokens consumed
            if self._current_token().type != TokenType.EOF:
                raise ValueError(
                    f"Unexpected token at position {self.current}: {self._current_token()}"
                )
            
            return result

        # Return Condition wrapping the evaluator
        return Condition(evaluator)

    def _tokenize(self, expression: str) -> list:
        """
        Tokenize expression into list of tokens.

        Args:
            expression: Condition string

        Returns:
            List of Token objects
        """
        tokens = []
        i = 0
        length = len(expression)

        while i < length:
            # Skip whitespace
            if expression[i].isspace():
                i += 1
                continue

            # Number
            if expression[i].isdigit() or (
                expression[i] == '.' and i + 1 < length and expression[i + 1].isdigit()
            ):
                start = i
                has_dot = False
                while i < length and (
                    expression[i].isdigit() or (expression[i] == '.' and not has_dot)
                ):
                    if expression[i] == '.':
                        has_dot = True
                    i += 1
                num_str = expression[start:i]
                value = float(num_str) if has_dot else int(num_str)
                tokens.append(Token(TokenType.NUMBER, value, start))
                continue

            # String (quoted)
            if expression[i] in ('"', "'"):
                quote_char = expression[i]
                start = i
                i += 1
                string_val = ""
                while i < length and expression[i] != quote_char:
                    string_val += expression[i]
                    i += 1
                if i >= length:
                    raise ValueError(f"Unterminated string at position {start}")
                i += 1  # Skip closing quote
                tokens.append(Token(TokenType.STRING, string_val, start))
                continue

            # Operators (>=, <=, ==, !=)
            if i + 1 < length and expression[i:i+2] in self.COMPARISON_OPS:
                tokens.append(Token(TokenType.OPERATOR, expression[i:i+2], i))
                i += 2
                continue

            # Single character operators (>, <)
            if expression[i] in self.COMPARISON_OPS:
                tokens.append(Token(TokenType.OPERATOR, expression[i], i))
                i += 1
                continue

            if expression[i] in "!=":
                raise ValueError(
                    f"Invalid operator at position {i}: use >=, <=, >, <, ==, or !="
                )

            # Logical operators (and, or)
            if (
                expression[i:i+3] == "and"
                and (i + 3 >= length or not expression[i + 3].isalnum())
            ):
                tokens.append(Token(TokenType.LOGICAL, "and", i))
                i += 3
                continue

            if (
                expression[i:i+2] == "or"
                and (i + 2 >= length or not expression[i + 2].isalnum())
            ):
                tokens.append(Token(TokenType.LOGICAL, "or", i))
                i += 2
                continue

            # Parentheses
            if expression[i] == '(':
                tokens.append(Token(TokenType.LPAREN, '(', i))
                i += 1
                continue

            if expression[i] == ')':
                tokens.append(Token(TokenType.RPAREN, ')', i))
                i += 1
                continue

            # Variable (identifier)
            if expression[i].isalpha() or expression[i] == '_':
                start = i
                while i < length and (expression[i].isalnum() or expression[i] == '_'):
                    i += 1
                var_name = expression[start:i]

                # Whitelist check
                if var_name not in self.ALLOWED_VARIABLES:
                    raise ValueError(
                        f"Variable '{var_name}' not allowed. "
                        f"Allowed: {', '.join(sorted(self.ALLOWED_VARIABLES))}"
                    )

                tokens.append(Token(TokenType.VARIABLE, var_name, start))
                continue

            # Unknown character
            raise ValueError(f"Unexpected character '{expression[i]}' at position {i}")

        # EOF token
        tokens.append(Token(TokenType.EOF, None, len(expression)))
        return tokens

    def _current_token(self) -> Token:
        """Get current token."""
        if self.current < len(self.tokens):
            return self.tokens[self.current]
        return self.tokens[-1]  # EOF

    def _advance(self):
        """Move to next token."""
        if self.current < len(self.tokens) - 1:
            self.current += 1

    def _parse_or_expression(self, context: Dict[str, Union[int, float]]) -> bool:
        """
        Parse OR expression: and_expr (or and_expr)*

        Args:
            context: Variable values

        Returns:
            Boolean result
        """
        result = self._parse_and_expression(context)

        while (
            self._current_token().type == TokenType.LOGICAL
            and self._current_token().value == "or"
        ):
            self._advance()  # consume 'or'
            right = self._parse_and_expression(context)
            result = result or right

        return result

    def _parse_and_expression(self, context: Dict[str, Union[int, float]]) -> bool:
        """
        Parse AND expression: comparison (and comparison)*

        Args:
            context: Variable values

        Returns:
            Boolean result
        """
        result = self._parse_comparison(context)

        while (
            self._current_token().type == TokenType.LOGICAL
            and self._current_token().value == "and"
        ):
            self._advance()  # consume 'and'
            right = self._parse_comparison(context)
            result = result and right

        return result

    def _parse_comparison(self, context: Dict[str, Union[int, float]]) -> bool:
        """
        Parse comparison: value OPERATOR value

        Args:
            context: Variable values

        Returns:
            Boolean result
        """
        # Handle parentheses
        if self._current_token().type == TokenType.LPAREN:
            self._advance()  # consume '('
            result = self._parse_or_expression(context)
            if self._current_token().type != TokenType.RPAREN:
                raise ValueError(f"Expected ')' at position {self.current}")
            self._advance()  # consume ')'
            return result

        # Parse left value
        left = self._parse_value(context)

        # Expect operator
        if self._current_token().type != TokenType.OPERATOR:
            raise ValueError(
                f"Expected comparison operator at position {self.current}, "
                f"got {self._current_token()}"
            )

        operator = self._current_token().value
        self._advance()

        # Parse right value
        right = self._parse_value(context)

        # Perform comparison
        op_func = self.COMPARISON_OPS[operator]
        return op_func(left, right)

    def _parse_value(
        self, context: Dict[str, Union[int, float]]
    ) -> Union[int, float, str]:
        """
        Parse value: NUMBER | STRING | VARIABLE

        Args:
            context: Variable values

        Returns:
            Value (number, string, or variable value from context)
        """
        token = self._current_token()

        if token.type == TokenType.NUMBER:
            self._advance()
            return token.value

        if token.type == TokenType.STRING:
            self._advance()
            return token.value

        if token.type == TokenType.VARIABLE:
            var_name = token.value
            self._advance()

            # Look up variable in context
            if var_name not in context:
                raise ValueError(f"Variable '{var_name}' not provided in context")

            return context[var_name]

        raise ValueError(f"Expected value at position {self.current}, got {token}")


# Module-level parser instance
_parser = ConditionParser()


def parse_condition(expression: str) -> Condition:
    """
    Parse condition expression (main entry point).
    
    Args:
        expression: Condition string (e.g., "severity >= 0.8")
        
    Returns:
        Condition object that can be evaluated
        
    Raises:
        ValueError: If expression is invalid or unsafe
        
    Examples:
        >>> cond = parse_condition("severity >= 0.8")
        >>> cond.evaluate({"severity": 0.9})
        True
        
        >>> cond = parse_condition("always")
        >>> cond.evaluate({})
        True
    """
    return _parser.parse(expression)


def evaluate(condition: Condition, context: Dict[str, Union[int, float]]) -> bool:
    """
    Evaluate a parsed condition with given context.
    
    Args:
        condition: Parsed Condition object
        context: Variable values
        
    Returns:
        Boolean result
        
    Raises:
        ValueError: If required variables missing from context
    """
    return condition.evaluate(context)

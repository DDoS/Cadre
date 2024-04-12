import string
from abc import ABCMeta, abstractmethod
from enum import Enum, auto
from typing import Generator, Union


class Filter:
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, source: tuple[int, int]):
        self._source = source

    @abstractmethod
    def to_sql(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    def __str__(self) -> str:
        raise NotImplementedError()


def parse_filter(source: str) -> Filter:
    tokens = _split_tokens(source)
    _ = next(tokens)
    expression = _parse_expression(tokens)

    token, indices = next(tokens)
    if token != '':
        raise ValueError(f'Unknown token from {indices[0]} to {indices[1]}: "{token}"')

    return expression


class _UnaryOperator(Enum):
    NOT = auto()


class _UnaryOperation(Filter):
    def __init__(self, source: tuple[int, int], operator: _UnaryOperator, operand: Filter):
        super().__init__(source)
        self._operator = operator
        self._operand = operand

    def to_sql(self) -> str:
        if self._operator == _UnaryOperator.NOT:
            token = 'NOT'
        else:
            raise ValueError(self._operator)

        return f'{token} ({self._operand.to_sql()})'

    def __str__(self) -> str:
        if self._operator == _UnaryOperator.NOT:
            token = 'not'
        else:
            raise ValueError(self._operator)

        return f'{token} ({self._operand})'


class _BinaryOperator(Enum):
    OR = auto()
    AND = auto()


class _BinaryOperation(Filter):
    def __init__(self, source: tuple[int, int], operator: _BinaryOperator,
                 left_operand: Filter, right_operand: Filter):
        super().__init__(source)
        self._operator = operator
        self._left_operand = left_operand
        self._right_operand = right_operand

    def to_sql(self) -> str:
        if self._operator == _BinaryOperator.OR:
            token = 'OR'
        elif self._operator == _BinaryOperator.AND:
            token = 'AND'
        else:
            raise ValueError(self._operator)

        return f'({self._left_operand.to_sql()}) {token} ({self._right_operand.to_sql()})'

    def __str__(self) -> str:
        if self._operator == _BinaryOperator.OR:
            token = 'or'
        elif self._operator == _BinaryOperator.AND:
            token = 'and'
        else:
            raise ValueError(self._operator)

        return f'({self._left_operand}) {token} ({self._right_operand})'


class _NamedAspect(Enum):
    LANDSCAPE = auto()
    PORTRAIT = auto()
    SQUARE = auto()


class _Aspect(Filter):
    def __init__(self, source: tuple[int, int], name: _NamedAspect):
        super().__init__(source)
        self._name = name

    def to_sql(self) -> str:
        if self._name == _NamedAspect.LANDSCAPE:
            token = '>'
        elif self._name == _NamedAspect.PORTRAIT:
            token = '<'
        elif self._name == _NamedAspect.SQUARE:
            token = '=='
        else:
            raise ValueError(self._name)

        return f'width {token} height'

    def __str__(self) -> str:
        if self._name == _NamedAspect.LANDSCAPE:
            return 'landscape'
        if self._name == _NamedAspect.PORTRAIT:
            return 'portrait'
        if self._name == _NamedAspect.SQUARE:
            return 'square'

        raise ValueError(self._name)


class _Favorite(Filter):
    def __init__(self, source: tuple[int, int]):
        super().__init__(source)

    def to_sql(self) -> str:
        return 'favorite'

    def __str__(self) -> str:
        return 'favorite'


class _BoolLiteral(Filter):
    def __init__(self, source: tuple[int, int], value: bool):
        super().__init__(source)
        self._value = value

    def to_sql(self) -> str:
        return '1' if self._value else '0'

    def __str__(self) -> str:
        return 'true' if self._value else 'false'


Tokenizer = Generator[tuple[str, tuple[int, int]], bool | None, None]
def _split_tokens(source: str) -> Tokenizer:
    separator_chars = string.whitespace
    operator_chars = string.punctuation
    number_chars = string.digits
    identifier_start_chars = string.ascii_letters
    identifier_continue_chars = identifier_start_chars + number_chars

    end = 0
    start = end
    repeat_next = yield '', (start, end)

    while True:
        while start < len(source) and source[start] in separator_chars:
            start += 1

        end = start
        if end >= len(source):
            break

        if source[end] in operator_chars:
            token_chars = operator_chars
        elif source[end] in number_chars:
            token_chars = number_chars
        elif source[end] in identifier_start_chars:
            token_chars = identifier_continue_chars
        else:
            raise ValueError(f'Unknown character at index {end}: "{ord(source[end])}"')
        end += 1

        while end < len(source) and source[end] in token_chars:
            end += 1

        while True:
            repeat = repeat_next
            repeat_next = yield source[start:end], (start, end)
            if not repeat:
                break

        start = end

    while True:
        yield '', (start, end)


_Atom = _Aspect | _Favorite | _BoolLiteral | Union['_Expression']
_Unary = _UnaryOperation | _Atom
_And = _BinaryOperation | _Unary
_Or = _BinaryOperation | _And
_Expression = _Or


def _parse_expression(tokens: Tokenizer) -> _Expression:
    return _parse_or(tokens)


def _parse_or(tokens: Tokenizer) -> _Or:
    def parse_or_right(tokens: Tokenizer, left_operand: _Unary) -> _Or:
        token, indices = tokens.send(True)
        if token != 'or':
            return left_operand

        _ = next(tokens)
        right_operand = _parse_and(tokens)
        left_operand = _BinaryOperation(indices, _BinaryOperator.OR, left_operand, right_operand)
        return parse_or_right(tokens, left_operand)

    left_operand = _parse_and(tokens)
    return parse_or_right(tokens, left_operand)


def _parse_and(tokens: Tokenizer) -> _And:
    def parse_and_right(tokens: Tokenizer, left_operand: _Unary) -> _And:
        token, indices = tokens.send(True)
        if token != 'and':
            return left_operand

        _ = next(tokens)
        right_operand = _parse_unary(tokens)
        left_operand = _BinaryOperation(indices, _BinaryOperator.AND, left_operand, right_operand)
        return parse_and_right(tokens, left_operand)

    left_operand = _parse_unary(tokens)
    return parse_and_right(tokens, left_operand)


def _parse_unary(tokens: Tokenizer) -> _Unary:
    token, indices = tokens.send(True)
    if token == 'not':
        _ = next(tokens)
        operand = _parse_atom(tokens)
        return _UnaryOperation(indices, _UnaryOperator.NOT, operand)

    return _parse_atom(tokens)


def _parse_atom(tokens: Tokenizer) -> _Atom:
    token, indices = next(tokens)
    if token == 'landscape':
        return _Aspect(indices, _NamedAspect.LANDSCAPE)
    if token == 'portrait':
        return _Aspect(indices, _NamedAspect.PORTRAIT)
    if token == 'square':
        return _Aspect(indices, _NamedAspect.SQUARE)
    if token == 'favorite':
        return _Favorite(indices)
    if token == 'true':
        return _BoolLiteral(indices, True)
    if token == 'false':
        return _BoolLiteral(indices, False)
    if token == '(':
        expression = _parse_expression(tokens)
        token, indices = next(tokens)
        if token != ')':
            raise ValueError(f'Expected ")" at {indices[0]}')

        return expression

    raise ValueError(f'Unknown token from {indices[0]} to {indices[1]}: "{token}"')

import string
from abc import ABCMeta, abstractmethod
from enum import Enum, auto
from typing import Generator, Union


class _TokenKind(Enum):
    START = auto()
    END = ()
    OPERATOR = auto()
    NUMBER = auto()
    IDENTIFIER = auto()


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

    token, token_kind, indices = next(tokens)
    match token_kind:
        case _TokenKind.END:
            return expression
        case _:
            raise ValueError(f'Unknown token from {indices[0]} to {indices[1]}: "{token}"')


class _UnaryOperator(Enum):
    NOT = auto()


class _UnaryOperation(Filter):
    def __init__(self, source: tuple[int, int], operator: _UnaryOperator, operand: Filter):
        super().__init__(source)
        self._operator = operator
        self._operand = operand

    def to_sql(self) -> str:
        match self._operator:
            case _UnaryOperator.NOT:
                token = 'NOT'
            case other:
                raise ValueError(other)

        return f'{token} ({self._operand.to_sql()})'

    def __str__(self) -> str:
        match self._operator:
            case _UnaryOperator.NOT:
                token = 'not'
            case other:
                raise ValueError(other)

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
        match self._operator:
            case _BinaryOperator.OR:
                token = 'OR'
            case _BinaryOperator.AND:
                token = 'AND'
            case other:
                raise ValueError(other)

        return f'({self._left_operand.to_sql()}) {token} ({self._right_operand.to_sql()})'

    def __str__(self) -> str:
        match self._operator:
            case _BinaryOperator.OR:
                token = 'or'
            case _BinaryOperator.AND:
                token = 'and'
            case other:
                raise ValueError(other)

        return f'({self._left_operand}) {token} ({self._right_operand})'


class _BoolLiteral(Filter):
    def __init__(self, source: tuple[int, int], value: bool):
        super().__init__(source)
        self._value = value

    def to_sql(self) -> str:
        return '1' if self._value else '0'

    def __str__(self) -> str:
        return 'true' if self._value else 'false'


class _NamedAspect(Enum):
    LANDSCAPE = auto()
    PORTRAIT = auto()
    SQUARE = auto()


class _Aspect(Filter):
    def __init__(self, source: tuple[int, int], name: _NamedAspect):
        super().__init__(source)
        self._name = name

    def to_sql(self) -> str:
        match self._name:
            case _NamedAspect.LANDSCAPE:
                token = '>'
            case _NamedAspect.PORTRAIT:
                token = '<'
            case _NamedAspect.SQUARE:
                token = '=='
            case other:
                raise ValueError(other)

        return f'photos.width {token} photos.height'

    def __str__(self) -> str:
        match self._name:
            case _NamedAspect.LANDSCAPE:
                return 'landscape'
            case _NamedAspect.PORTRAIT:
                return 'portrait'
            case _NamedAspect.SQUARE:
                return 'square'
            case other:
                raise ValueError(other)


class _Favorite(Filter):
    def __init__(self, source: tuple[int, int]):
        super().__init__(source)

    def to_sql(self) -> str:
        return 'COALESCE(photos.favorite, 0)'

    def __str__(self) -> str:
        return 'favorite'


class _IdentifierSet(Filter):
    def __init__(self, source: tuple[int, int], identifiers: set[str]):
        super().__init__(source)
        self._identifiers = identifiers

    def to_sql(self) -> str:
        return " OR ".join(f'collections.identifier = "{identifier}"' for identifier in self._identifiers)

    def __str__(self) -> str:
        return f'{{{" ".join(self._identifiers)}}}'


Tokenizer = Generator[tuple[str, _TokenKind, tuple[int, int]], bool | None, None]
def _split_tokens(source: str) -> Tokenizer:
    separator_chars = string.whitespace
    operator_set = {'(', ')', '{', '}'}
    operator_chars = set(''.join(operator_set))
    number_chars = string.digits
    identifier_start_chars = string.ascii_letters
    identifier_continue_chars = identifier_start_chars + number_chars

    def consume_char(index: int, token_chars: str):
        return index < len(source) and source[index] in token_chars

    end = 0
    start = end

    def continue_token(token_chars: str, token_set: set[str] = {}):
        if source[start:end] in token_set:
            return False

        return consume_char(end, token_chars)

    repeat_next = yield '', _TokenKind.START, (start, end)

    while True:
        while consume_char(start, separator_chars):
            start += 1

        end = start
        if end >= len(source):
            break

        token_set = {}
        if source[end] in operator_chars:
            token_chars = operator_chars
            token_set = operator_set
            token_kind = _TokenKind.OPERATOR
        elif source[end] in number_chars:
            token_chars = number_chars
            token_kind = _TokenKind.NUMBER
        elif source[end] in identifier_start_chars:
            token_chars = identifier_continue_chars
            token_kind = _TokenKind.IDENTIFIER
        else:
            raise ValueError(f'Invalid character at index {end}: 0x{ord(source[end]):X}')
        end += 1

        while continue_token(token_chars, token_set):
            end += 1

        while True:
            repeat = repeat_next
            repeat_next = yield source[start:end], token_kind, (start, end)
            if not repeat:
                break

        start = end

    while True:
        yield '', _TokenKind.END, (start, end)


_Atom = _Aspect | _Favorite | _BoolLiteral | Union['_Expression']
_Unary = _UnaryOperation | _Atom
_And = _BinaryOperation | _Unary
_Or = _BinaryOperation | _And
_Expression = _Or


def _parse_expression(tokens: Tokenizer) -> _Expression:
    return _parse_or(tokens)


def _parse_or(tokens: Tokenizer) -> _Or:
    def parse_or_right(tokens: Tokenizer, left_operand: _Unary) -> _Or:
        token, _, indices = tokens.send(True)
        match token:
            case 'or':
                _ = next(tokens)
                right_operand = _parse_and(tokens)
                left_operand = _BinaryOperation(indices, _BinaryOperator.OR, left_operand, right_operand)
                return parse_or_right(tokens, left_operand)
            case _:
                return left_operand

    left_operand = _parse_and(tokens)
    return parse_or_right(tokens, left_operand)


def _parse_and(tokens: Tokenizer) -> _And:
    def parse_and_right(tokens: Tokenizer, left_operand: _Unary) -> _And:
        token, _, indices = tokens.send(True)
        match token:
            case 'and':
                _ = next(tokens)
                right_operand = _parse_unary(tokens)
                left_operand = _BinaryOperation(indices, _BinaryOperator.AND, left_operand, right_operand)
                return parse_and_right(tokens, left_operand)
            case _:
                return left_operand

    left_operand = _parse_unary(tokens)
    return parse_and_right(tokens, left_operand)


def _parse_unary(tokens: Tokenizer) -> _Unary:
    token, _, indices = tokens.send(True)
    match token:
        case 'not':
            _ = next(tokens)
            operand = _parse_atom(tokens)
            return _UnaryOperation(indices, _UnaryOperator.NOT, operand)
        case _:
            return _parse_atom(tokens)


def _parse_atom(tokens: Tokenizer) -> _Atom:
    token, _, indices = next(tokens)
    match token:
        case 'landscape':
            return _Aspect(indices, _NamedAspect.LANDSCAPE)
        case 'portrait':
            return _Aspect(indices, _NamedAspect.PORTRAIT)
        case 'square':
            return _Aspect(indices, _NamedAspect.SQUARE)
        case 'favorite':
            return _Favorite(indices)
        case 'true':
            return _BoolLiteral(indices, True)
        case 'false':
            return _BoolLiteral(indices, False)
        case '(':
            expression = _parse_expression(tokens)
            token, _, indices = next(tokens)
            match token:
                case ')':
                    return expression
                case other:
                    raise ValueError(f'Expected ")" at position {indices[0]}, but got "{other}"')
        case '{':
            identifiers = set()
            while True:
                token, token_kind, indices = next(tokens)
                match token, token_kind:
                    case [identifier, _TokenKind.IDENTIFIER]:
                        identifiers.add(identifier)
                    case ['}', _]:
                        if not identifiers:
                            raise ValueError(f'Expected identifier an at position {indices[0]}, but got "}}"')

                        return _IdentifierSet(indices, identifiers)
                    case _:
                        raise ValueError(f'Expected an identifier or "}}" at position {indices[0]}, but got "{other}"')
        case other:
            raise ValueError(f'Unknown token from {indices[0]} to {indices[1]}: "{other}"')

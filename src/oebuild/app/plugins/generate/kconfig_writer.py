"""
Kconfig writer with lightweight block/indent helpers.
"""

from __future__ import annotations

from typing import Iterable, List, Optional


class KconfigWriter:
    """Helper for emitting Kconfig text with consistent indentation."""

    INDENT = '    '
    HELP_INDENT = '  '

    def __init__(self) -> None:
        self._lines: List[str] = []
        self._indent_level = 0
        self._block_stack: List[tuple[str, int]] = []
        self._errors: List[str] = []

    def _indent(self, levels: int = 1) -> 'KconfigWriter':
        if levels < 0:
            raise ValueError('Indent levels must be non-negative')
        self._indent_level += levels
        return self

    def _dedent(self, levels: int = 1) -> 'KconfigWriter':
        if levels < 0:
            raise ValueError('Dedent levels must be non-negative')
        if self._indent_level < levels:
            raise ValueError('Cannot dedent below zero')
        self._indent_level -= levels
        return self

    def _add_line(self, content: str = '') -> 'KconfigWriter':
        if content:
            prefix = self.INDENT * self._indent_level
            self._lines.append(f'{prefix}{content}')
        else:
            self._lines.append('')
        return self

    def _pop_block(self, expected: str) -> tuple[str, int]:
        if not self._block_stack:
            raise ValueError(f'Unexpected end_{expected} without begin')
        name, delta = self._block_stack.pop()
        if name != expected:
            raise ValueError(f'Expected end_{expected}, got end_{name}')
        return name, delta

    def line(self, content: str = '') -> 'KconfigWriter':
        return self._add_line(content)

    def blank(self) -> 'KconfigWriter':
        return self._add_line('')

    def indent(self, levels: int = 1) -> 'KconfigWriter':
        return self._indent(levels)

    def dedent(self, levels: int = 1) -> 'KconfigWriter':
        return self._dedent(levels)

    def menu(self, prompt: str, indent_body: bool = True) -> 'KconfigWriter':
        self._add_line(f'menu "{self.escape(prompt)}"')
        delta = 1 if indent_body else 0
        self._block_stack.append(('menu', delta))
        if delta:
            self._indent(delta)
        return self

    def end_menu(self) -> 'KconfigWriter':
        _, delta = self._pop_block('menu')
        if delta:
            self._dedent(delta)
        self._add_line('endmenu')
        return self

    def choice(
        self,
        prompt: Optional[str] = None,
        default: Optional[str] = None,
        depends_on: Optional[str] = None,
    ) -> 'KconfigWriter':
        self._add_line('choice')
        self._block_stack.append(('choice', 1))
        self._indent(1)
        if prompt is not None:
            self._add_line(f'prompt "{self.escape(prompt)}"')
        if depends_on:
            self._add_line(f'depends on {depends_on}')
        if default is not None:
            self._add_line(f'default {default}')
        return self

    def end_choice(self) -> 'KconfigWriter':
        _, delta = self._pop_block('choice')
        if delta:
            self._dedent(delta)
        self._add_line('endchoice')
        return self

    def if_(self, condition: str) -> 'KconfigWriter':
        self._add_line(f'if {condition}')
        self._block_stack.append(('if', 1))
        self._indent(1)
        return self

    def end_if(self) -> 'KconfigWriter':
        _, delta = self._pop_block('if')
        if delta:
            self._dedent(delta)
        self._add_line('endif')
        return self

    def config(
        self,
        symbol: str,
        prompt: Optional[str] = None,
        type_: Optional[str] = 'bool',
        default: Optional[str] = None,
        depends_on: Optional[str | Iterable[str]] = None,
        select: Optional[str | Iterable[str]] = None,
        help_lines: Optional[List[str]] = None,
    ) -> 'KconfigWriter':
        self._add_line(f'config {symbol}')
        self._indent(1)
        if type_:
            if prompt is not None:
                self._add_line(f'{type_} "{self.escape(prompt)}"')
            else:
                self._add_line(type_)
        if help_lines:
            self._add_line('help')
            help_prefix = (
                f'{self.INDENT * self._indent_level}{self.HELP_INDENT}'
            )
            for line in help_lines:
                self._lines.append(f'{help_prefix}{line}')
        if default is not None:
            self._add_line(f'default {self._format_default(default)}')
        depends_expr = self._format_depends(depends_on)
        if depends_expr:
            self._add_line(f'depends on {depends_expr}')
        for select_id in self._format_list(select):
            self._add_line(f'select {select_id}')
        self._dedent(1)
        return self

    def source(self, path: str) -> 'KconfigWriter':
        self._add_line(f'source "{path}"')
        return self

    def lines(self) -> List[str]:
        return list(self._lines)

    def text(self) -> str:
        return '\n'.join(self._lines)

    def get_lines(self) -> List[str]:
        return self.lines()

    def get_text(self) -> str:
        return self.text()

    def validate(self) -> bool:
        self._errors = []
        if self._indent_level != 0:
            self._errors.append(
                f'Indentation not balanced: {self._indent_level}'
            )
        if self._block_stack:
            open_blocks = ', '.join(name for name, _ in self._block_stack)
            self._errors.append(f'Unclosed blocks: {open_blocks}')
        return not self._errors

    def errors(self) -> List[str]:
        return list(self._errors)

    def escape(self, prompt: str) -> str:
        return prompt.replace('"', '\\"')

    def escape_prompt(self, prompt: str) -> str:
        return self.escape(prompt)

    def _format_list(self, value: Optional[str | Iterable[str]]) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [item for item in value if item]

    def _format_depends(
        self, depends_on: Optional[str | Iterable[str]]
    ) -> Optional[str]:
        if depends_on is None:
            return None
        if isinstance(depends_on, str):
            return depends_on
        parts = [entry for entry in depends_on if entry]
        if not parts:
            return None
        return ' && '.join(parts)

    def _format_default(self, default: str) -> str:
        if isinstance(default, bool):
            return 'y' if default else 'n'
        return str(default)

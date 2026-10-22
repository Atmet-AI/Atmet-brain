"""Human terminal presentation, with plain and JSON paths for automation."""

import os
import re
import shutil
import sys
import textwrap

from ._version import __version__


def clean(value):
    # Do not let imported source text or names issue terminal control sequences.
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", str(value)).replace("\r", "")


class Console:
    def __init__(self, stream=None, plain=False):
        self.stream = stream or sys.stderr
        self.color = self.stream.isatty() and not plain and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"

    def line(self, value="", accent=False):
        value = clean(value)
        if accent and self.color:
            value = "\033[1m" + value + "\033[0m"
        print(value, file=self.stream)

    def banner(self, subtitle="Company memory. Current procedures. Your agents."):
        self.line()
        self.line("  A T M E T   /   B R A I N", accent=True)
        self.line("  " + __version__ + "  |  " + subtitle)
        self.line()

    def result(self, value, indent=2):
        prefix = " " * indent
        if isinstance(value, dict):
            for key, item in value.items():
                label = key.replace("_", " ").capitalize()
                if isinstance(item, (list, dict)):
                    self.line(prefix + label, accent=True)
                    self.result(item, indent + 2)
                else:
                    self.wrapped(f"{label}: {item}", prefix)
        elif isinstance(value, list):
            if not value:
                self.line(prefix + "No items yet.")
            for item in value:
                if isinstance(item, (dict, list)):
                    self.result(item, indent)
                    self.line()
                else:
                    self.wrapped(str(item), prefix + "- ")
        else:
            self.wrapped(str(value), prefix)

    def wrapped(self, value, prefix):
        width = max(40, shutil.get_terminal_size().columns)
        for paragraph in clean(value).splitlines() or [""]:
            for line in textwrap.wrap(paragraph, width=width, initial_indent=prefix,
                                      subsequent_indent=" " * len(prefix), break_long_words=False, break_on_hyphens=False) or [prefix]:
                self.line(line)


def prompt(label, default=None, choices=None):
    from .errors import BrainError
    suffix = f" [{default}]" if default is not None else ""
    while True:
        try:
            value = input(clean(label) + suffix + ": ").strip() or default
        except EOFError:
            raise BrainError("setup_interrupted", "Setup needs answers. Use setup flags for non-interactive use.") from None
        if value and (not choices or value in choices):
            return value
        print("Choose " + ", ".join(choices) if choices else "Enter a value.", file=sys.stderr)

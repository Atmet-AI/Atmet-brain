"""Human terminal presentation, with plain and JSON paths for automation."""

import json
import os
import re
import shutil
import sys
import textwrap

from ._version import __version__

# A terminal-only display treatment, not a replacement for the brand's SVG mark.
PIXELS = {
    "A": ("01110", "11011", "11011", "11111", "11011", "11011"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100"),
    "M": ("10001", "11011", "11111", "10101", "10001", "10001"),
    "E": ("11111", "10000", "11110", "10000", "10000", "11111"),
}
WORDMARK = tuple("  ".join("".join("██" if bit == "1" else "  " for bit in PIXELS[letter][row])
                           for letter in "ATMET").rstrip() for row in range(6))


def clean(value):
    # Do not let imported source text or names issue terminal control sequences.
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", str(value)).replace("\r", "")


class Console:
    def __init__(self, stream=None, plain=False):
        self.stream = stream or sys.stderr
        self.color = self.stream.isatty() and not plain and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"
        self.width = max(20, shutil.get_terminal_size().columns)
        depth = os.environ.get("COLORTERM", "").lower()
        self.orange = "38;2;245;83;21" if depth in {"truecolor", "24bit"} else (
            "38;5;202" if "256" in os.environ.get("TERM", "") else "33")
        try:
            "█─".encode(getattr(self.stream, "encoding", None) or "utf-8")
            self.unicode = True
        except (UnicodeError, LookupError):
            self.unicode = False

    def styled(self, value, accent=False, muted=False):
        value = clean(value)
        if self.color and (accent or muted):
            code = self.orange if accent else "2"
            return "\033[" + code + "m" + value + "\033[0m"
        return value

    def line(self, value="", accent=False, muted=False):
        print(self.styled(value, accent, muted), file=self.stream)

    def banner(self, subtitle="Company memory. Workflows. Your agents.", compact=False):
        self.line()
        if not compact and self.color and self.unicode and self.width >= max(map(len, WORDMARK)) + 4:
            for row in WORDMARK:
                self.line("  " + row, accent=True)
            self.line()
            self.line("  Atmet Brain  /  " + __version__)
        else:
            self.line("  Atmet Brain  /  " + __version__, accent=True)
        self.wrapped(subtitle, "  ", muted=True)
        self.line("  " + ("─" if self.unicode else "-") * min(58, self.width - 4), muted=True)
        self.line()

    def welcome(self, value):
        self.banner()
        self.line("  Welcome back." if value["initialized"] else "  Start with your company.")
        self.wrapped("Build one department and one workflow, then connect your agents.", "  ", muted=True)
        self.line()
        self.wrapped("Home  " + value["home"], "  ", muted=True)
        self.line()
        for title, command in [("Set up a Brain", value["start"]), ("Inspect this Brain", value["inspect"]),
                               ("Connect an agent", value["agent"]),
                               ("Host a team Brain", value["host"]), ("Join your team", value["join"]),
                               ("Browse commands", value["help"])]:
            self.line("  " + title)
            self.wrapped(command, "    ", accent=True)
            self.line()
        if value["connections"]:
            self.wrapped("Saved connections: " + str(len(value["connections"])) + ". Use atmet-brain connections list.", "  ", muted=True)

    def option(self, name, title, description):
        self.line("  " + name + "  /  " + title, accent=True)
        self.wrapped(description, "    ", muted=True)
        self.line()

    def agent_ready(self, value):
        self.banner("Your agent connection is ready to add.", compact=True)
        self.line("  Core access verified", accent=True)
        self.wrapped("Workspaces: " + ", ".join(value["workspaces"]), "  ")
        self.wrapped("Access: " + value["access_description"], "  ")
        self.wrapped("Identity: " + value["identity"]["name"], "  ")
        self.line()
        for index, step in enumerate(value["next"], 1):
            self.wrapped(str(index) + ". " + step, "  ", accent=index == 1)
        if value["method"] == "mcp":
            self.line()
            self.line("  Copy this MCP entry, or use the saved mcp.json file:", accent=True)
            for line in json.dumps(value["mcp_entry"], indent=2, ensure_ascii=False).splitlines():
                self.line(line)
        self.line()
        self.wrapped("Private setup folder: " + value["directory"], "  ", muted=True)
        self.wrapped("External agent connection has not been tested. Skill publication remains a separate authorized decision.", "  ", muted=True)

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

    def wrapped(self, value, prefix, accent=False, muted=False):
        width = self.width
        for paragraph in clean(value).splitlines() or [""]:
            for line in textwrap.wrap(paragraph, width=width, initial_indent=prefix,
                                      subsequent_indent=" " * len(prefix), break_long_words=False, break_on_hyphens=False) or [prefix]:
                self.line(line, accent, muted)


def prompt(label, default=None, choices=None, *, console=None):
    from .errors import BrainError
    console = console or Console()
    suffix = f" [{default}]" if default is not None else ""
    while True:
        try:
            # Prompts belong on stderr so redirected stdout stays valid JSON.
            print(console.styled("  > ", accent=True) + clean(label) + clean(suffix) + ": ",
                  end="", file=console.stream, flush=True)
            value = input().strip() or default
        except EOFError:
            raise BrainError("setup_interrupted", "This guided flow needs answers. Use command flags for non-interactive use.") from None
        if value and (not choices or value in choices):
            return value
        console.line("  Choose " + ", ".join(choices) if choices else "  Enter a value.")

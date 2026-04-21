"""Rosetta CLI — composable tools for semantic schema mapping."""

from __future__ import annotations

import importlib
import os
import sys

import click

_LAZY_SUBCOMMANDS: dict[str, str] = {
    "ingest": "rosetta.cli.ingest",
    "translate": "rosetta.cli.translate",
    "embed": "rosetta.cli.embed",
    "suggest": "rosetta.cli.suggest",
    "lint": "rosetta.cli.lint",
    "validate": "rosetta.cli.validate",
    "compile": "rosetta.cli.compile",
    "run": "rosetta.cli.run",
    "accredit": "rosetta.cli.accredit",
    "shacl-gen": "rosetta.cli.shacl_gen",
}


class LazyGroup(click.Group):
    """Click group that defers subcommand imports until invocation."""

    def __init__(
        self,
        name: str | None = None,
        lazy_subcommands: dict[str, str] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(name=name, **kwargs)  # pyright: ignore[reportArgumentType]
        self.lazy_subcommands: dict[str, str] = lazy_subcommands or {}

    def list_commands(self, ctx: click.Context) -> list[str]:  # pyright: ignore[reportImplicitOverride]
        base = super().list_commands(ctx)
        lazy = sorted(self.lazy_subcommands.keys())
        return base + lazy

    def get_command(  # pyright: ignore[reportImplicitOverride,reportIncompatibleMethodOverride]
        self, ctx: click.Context, cmd_name: str
    ) -> click.BaseCommand | None:
        if cmd_name in self.lazy_subcommands:
            module_path = self.lazy_subcommands[cmd_name]
            mod = importlib.import_module(module_path)
            cmd: click.BaseCommand = mod.cli  # pyright: ignore[reportAny]
            return cmd
        return super().get_command(ctx, cmd_name)


@click.group(cls=LazyGroup, lazy_subcommands=_LAZY_SUBCOMMANDS)
@click.version_option(package_name="rosetta-cli", prog_name="rosetta")
@click.option(
    "-v", "--verbose", is_flag=True, default=False, help="Enable verbose output on stderr."
)
@click.option(
    "-q", "--quiet", is_flag=True, default=False, help="Suppress all output except errors."
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool) -> None:
    """Rosetta — composable CLI tools for semantic schema mapping."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


def main() -> None:
    try:
        cli()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(141)

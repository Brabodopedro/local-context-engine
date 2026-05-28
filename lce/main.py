from __future__ import annotations

import typer

from lce.cli.doctor_cmd import doctor
from lce.cli.init_cmd import init
from lce.cli.prompt_cmd import prompt
from lce.cli.scan_cmd import scan
from lce.cli.task_cmd import task

app = typer.Typer(
    name="lce",
    help="Local Context Engine: deterministic repository context for AI coding agents.",
    no_args_is_help=True,
)

app.command("init")(init)
app.command("scan")(scan)
app.command("task")(task)
app.command("prompt")(prompt)
app.command("doctor")(doctor)


if __name__ == "__main__":
    app()

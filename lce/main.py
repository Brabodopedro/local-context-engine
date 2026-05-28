from __future__ import annotations

import typer

from lce.cli.doctor_cmd import doctor
from lce.cli.init_cmd import init
from lce.cli.prompt_cmd import prompt
from lce.cli.scan_cmd import scan
from lce.cli.spec_cmd import spec
from lce.cli.task_cmd import task
from lce.cli.update_cmd import update

app = typer.Typer(
    name="lce",
    help="Local Context Engine: deterministic repository context for AI coding agents.",
    no_args_is_help=True,
)

app.command("init")(init)
app.command("scan")(scan)
app.command("task")(task)
app.command("spec")(spec)
app.command("prompt")(prompt)
app.command("doctor")(doctor)
app.command("update")(update)


if __name__ == "__main__":
    app()

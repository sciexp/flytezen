import rich_click as click

from flytezen import __version__
from flytezen.cli.execute import main as execute_main


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.version_option(version=__version__, prog_name="flytezen")
def main():
    click.echo("flytezen")


@main.command("execute")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def execute(args):
    execute_main(args)

# import rich_click as click

# from flytezen import __version__
from flytezen.cli.execute import main as execute_main

# from flytezen.logging_utils import configure_logging

# logger = configure_logging("flytezen")

# @click.group(
#     context_settings={"help_option_names": ["-h", "--help"]},
#     invoke_without_command=True,
# )
# @click.version_option(version=__version__, prog_name="flytezen")
# def main():
#     click.echo("flytezen")


# @main.command()
# def execute():
#     execute_main(logger)
def main():
    execute_main()

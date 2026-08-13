"""Load and render the UI's package-owned HTML templates."""

from functools import cache
from importlib.resources import files
from string import Template

_PACKAGE = "ddd_harness_engineering"


@cache
def load_template(name: str) -> str:
    """Load a UTF-8 template relative to the package's template directory."""
    return files(_PACKAGE).joinpath("templates", name).read_text(encoding="utf-8")


def render_template(name: str, /, **context: object) -> str:
    """Render a template using explicit ``$name`` placeholders."""
    values = {key: str(value) for key, value in context.items()}
    return Template(load_template(name)).substitute(values)

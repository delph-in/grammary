"""Generate an HTML table from the grammary TOML manifest."""

import toml


def generate_html_table(toml_file: str, output_html: str) -> None:
    """Write an HTML table of grammar name, size, source, and treebank fields.

    Args:
        toml_file: Path to the grammary TOML manifest.
        output_html: Output path for the generated HTML table.
    """
    data = toml.load(toml_file)

    all_keys = "size vcs trb".split()
    headers = "Name Size Source Treebank".split()

    with open(output_html, "w", encoding="utf-8") as out:
        out.write("<table>\n")
        out.write("  <thead>\n    <tr>\n")
        for header in headers:
            out.write(f"      <th>{header}</th>\n")
        out.write("    </tr>\n  </thead>\n")
        out.write("  <tbody>\n")
        for name, section in data.items():
            out.write("    <tr>\n")
            out.write(f"      <th align='left'>{name}</th>\n")
            for key in all_keys:
                val = section.get(key, "")
                out.write(f"      <td>{val}</td>\n")
            out.write("    </tr>\n")
        out.write("  </tbody>\n</table>\n")


if __name__ == "__main__":
    generate_html_table("grammary.toml", "grammary-table.md")

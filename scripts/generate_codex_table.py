import toml

def generate_html_table(toml_file, output_html):
    data = toml.load(toml_file)

    # Keys to use in the table
    all_keys = "size vcs trb".split()

    headers = "Name Size Source Treebank".split()
    rows = []

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

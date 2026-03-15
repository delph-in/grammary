"""Generate docs/grammary-table.md from grammary.toml."""

import argparse

import toml


def generate_md_table(toml_file, output_md):
    data = toml.load(toml_file)

    headers = ["Name", "Size", "Source", "Treebank"]
    keys = ["size", "vcs", "trb"]

    with open(output_md, "w", encoding="utf-8") as out:
        out.write("| " + " | ".join(headers) + " |\n")
        out.write("| " + " | ".join("---" for _ in headers) + " |\n")
        for name, section in data.items():
            row = [name] + [section.get(k, "") for k in keys]
            out.write("| " + " | ".join(str(v) for v in row) + " |\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toml", default="grammary.toml")
    parser.add_argument("--output", default="docs/grammary.md")
    args = parser.parse_args()
    generate_md_table(args.toml, args.output)
    print(f"Table written to {args.output}")

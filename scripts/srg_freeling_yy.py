#!/usr/bin/env python3
"""srg_freeling_yy.py

Spanish -> DELPH-IN YY lattice preprocessor for the SRG, via FreeLing's
`analyze` CLI instead of its Python bindings (pyfreeling_api).

Why this exists: the SRG's own wrapper (build/srg/util/analyze-wrappers/
srg-yy.sh -> srg_freeling2yy.py -> tokenize_and_tag.py) calls FreeLing
through pyfreeling_api, a compiled extension built against one exact
Python ABI. On Ubuntu 24.04 ("noble") that extension won't even load:
neither the copy vendored in the SRG checkout (built for Python 3.8) nor
the one shipped in the FreeLing .deb itself (built for Python 3.10)
matches the system's Python 3.12, and even supplying a matching Python
ABI doesn't help, since libfreeling.so itself was linked against a
jammy-built boost_regex (ICU 70 symbol namespace) that noble's rebuilt
boost1.74.0 package (ICU 74 namespace) can't satisfy. The plain `analyze`
CLI has none of these problems, so this script reimplements the analysis
step via two `analyze` subprocess calls, reusing the SRG's own, unmodified
override_tag/override_lemma (imported straight from srg_freeling2yy.py) for
the grammar-specific tag remapping rules in override_freeling.py and
srg-freeling.dat, so those stay exactly as upstream maintains them.

The final YY-string assembly (_render_pos/_convert_sentence below), unlike
override_tag/override_lemma, is NOT a straight reuse of
srg_freeling2yy.convert_sentences -- that function's literal string template
turned out to mishandle retokenizable words (clitic attachments like
"creerlo") when checked against ACE directly: it emits the same
multi-rule-name string for both the lrule list and the POS-tag list, but
ACE requires a probability after every POS-tag entry while the lrule list
must stay bare names with none -- a single probability for a two-tag
postag list silently drops the second tag's lexical rule (ACE then reports
"lexemes do not span position N"). Confirmed by testing the corrected
version through ACE with build/DBS/SRG_1008.dat: it produces a sensible
reading (right predicate, right clitic argument) where the literal port did
not. See _render_pos's docstring for specifics.

Usage: one raw Spanish sentence on stdin; one YY lattice line on stdout.
Matches the CommandAnalyzer contract in etc/ltdb/web/preprocess.py
(SRG_YY_CMD), which pipes a single sentence in and reads one line back.

This talks to two persistent FreeLing server processes (one per analysis
pass -- a server is locked to whatever flags it started with, and the two
passes need different flags) rather than spawning `analyze` fresh each call,
since a cold `analyze` process takes ~3s to load its dictionaries. See
scripts/freeling_server/README.md for how those servers are set up and run.

Environment:
    SRG_UTIL_DIR             Path to the SRG's build/srg/util/ checkout
                             (default: <repo root>/build/srg/util; override
                             on deployments where that tree is staged
                             somewhere else, e.g. /var/www/ltdb/srg-util)
    SRG_FREELING_TAGGED_PORT Port of the tagged-pass FreeLing server
                             (default 5031; see scripts/freeling_server/)
    SRG_FREELING_MORFO_PORT  Port of the morfo-pass FreeLing server
                             (default 5032; see scripts/freeling_server/)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRG_UTIL = Path(os.environ.get("SRG_UTIL_DIR", str(REPO_ROOT / "build" / "srg" / "util")))
SRG_FREELING_DAT = SRG_UTIL / "freeling_api" / "srg-freeling.dat"

_ANALYZE_TIMEOUT = 20
_TAGGED_PORT = os.environ.get("SRG_FREELING_TAGGED_PORT", "5031")
_MORFO_PORT = os.environ.get("SRG_FREELING_MORFO_PORT", "5032")


def _stub_pyfreeling_api() -> None:
    """Make `tokenize_and_tag.py`'s module-level pyfreeling_api import a no-op.

    We only need srg_freeling2yy's pure-Python override_tag/override_lemma,
    never Freeling_tok_tagger itself, but importing the module still runs
    `from tokenize_and_tag import Freeling_tok_tagger` at
    the top, which in turn does `from freeling_api.python_API import
    pyfreeling_api` -- the broken compiled extension. Pre-registering a
    harmless stub lets that import line succeed without ever touching the
    real (unloadable) extension.
    """
    freeling_api_pkg = types.ModuleType("freeling_api")
    python_api_pkg = types.ModuleType("freeling_api.python_API")
    python_api_pkg.pyfreeling_api = types.ModuleType("freeling_api.python_API.pyfreeling_api")
    freeling_api_pkg.python_API = python_api_pkg
    sys.modules.setdefault("freeling_api", freeling_api_pkg)
    sys.modules.setdefault("freeling_api.python_API", python_api_pkg)
    sys.modules.setdefault("freeling_api.python_API.pyfreeling_api", python_api_pkg.pyfreeling_api)


_stub_pyfreeling_api()
sys.path.insert(0, str(SRG_UTIL))
import override_freeling as ov
import parse_sppp_dat
import srg_freeling2yy as s2yy  # reuses its override_tag/override_lemma only; see module docstring


def _analyze(sentence: str, port: str) -> list[dict]:
    """Query a persistent FreeLing server over loopback and return its tokens.

    Args:
        sentence: Raw input sentence (no trailing newline required).
        port: Port of the (already warm) FreeLing server to query -- see
            _TAGGED_PORT/_MORFO_PORT. Each server is bound to a fixed set of
            analysis flags (see scripts/freeling_server/), so which port to
            use determines which pass this call performs.

    Returns:
        The token dict list for the (single) analyzed sentence, or an empty
        list if FreeLing produced no analysis or the server is unreachable.
    """
    proc = subprocess.run(
        ["analyzer_client", f"127.0.0.1:{port}"],
        input=sentence, capture_output=True, text=True,
        timeout=_ANALYZE_TIMEOUT, check=True,
    )
    data = json.loads(proc.stdout) if proc.stdout.strip() else []
    if not data:
        return []
    return data[0].get("tokens", [])


def _glue(tag: str) -> str:
    """Rebuild srg_freeling2yy's '+'-fusion glue string from a clean CLI tag.

    `analyze --nortk` reports a retokenizable multiword (e.g. the clitic
    attachment in "creerlo") as a single clean "TAG1+TAG2" string. The SRG's
    own code (tokenize_and_tag.py / srg-freeling.dat's <Fusion> section)
    instead builds and matches a slightly different glued form,
    `TAG1" "+TAG2`, so we reconstruct that exact shape before handing the
    tag to override_tag/the fuse dict -- only the glue differs, the lookup
    logic that consumes it is untouched. The leading "+" on the second part
    is not a separator; it is literally part of that inflectional rule's own
    name (inflr.tdl defines `+PP3MSA0` etc. for enclitic attachment).
    """
    parts = tag.split("+")
    return '" "+'.join(parts)


def _build_tokens(sentence: str, override_dicts: dict) -> list[dict]:
    """Produce the per-arc token list that _convert_sentence expects.

    This is the CLI-based replacement for tokenize_and_tag.Freeling_tok_tagger
    .tokenize_and_tag(): it decides, per word, whether to keep FreeLing's
    selected analysis, substitute a `<ReplaceAll>` entry from
    srg-freeling.dat, or (for words in `<NoDisambiguate>`) also expose the
    analyses FreeLing did not select as extra lattice arcs -- the same three
    cases get_selected_tags() in tokenize_and_tag.py handles, just sourced
    from two `analyze` JSON passes instead of pyfreeling_api Word objects.
    """
    selected = _analyze(sentence, _TAGGED_PORT)
    no_disambiguate = override_dicts["no_disambiguate"]
    need_morfo = any(tok["form"].lower() in no_disambiguate for tok in selected)
    morfo_by_span: dict[tuple[str, str], dict] = {}
    if need_morfo:
        for tok in _analyze(sentence, _MORFO_PORT):
            morfo_by_span[(tok["begin"], tok["end"])] = tok

    tokens: list[dict] = []
    for tok in selected:
        form = tok["form"]
        word = form.lower()
        start, end = int(tok["begin"]), int(tok["end"])
        is_retokenizable = "+" in tok["tag"]

        additional_arcs: list[dict] = []

        if is_retokenizable:
            # FreeLing's own fused lemma ("creer+lo") isn't what the grammar's
            # base lexicon is keyed on -- only the verb stem is ("creer"); the
            # clitic's contribution comes purely from the +PP3MSA0-style
            # inflectional rule's own suffixation (inflr.tdl), not from the
            # lemma string. Confirmed against ACE: keeping the fused lemma
            # here silently kills the reading (lexicon lookup for "creer+lo"
            # fails), even though the tag/rule chain is otherwise identical.
            base_lemma = tok["lemma"].split("+")[0]
            primary = {
                "lemma": base_lemma, "form": form, "start": start, "end": end,
                "tag": _glue(tok["tag"]), "prob": 1.0,
            }
        elif word in override_dicts["replace"]:
            entry = override_dicts["replace"][word]
            seen: set[tuple[str, str]] = set()
            primary = None
            for i, (rtag, rlemma) in enumerate(zip(entry["tag"], entry["lemma"])):
                if (rtag, rlemma) in seen:
                    continue
                seen.add((rtag, rlemma))
                arc = {"lemma": rlemma, "form": form, "start": start, "end": end,
                       "tag": rtag, "prob": -1, "additional": i > 0}
                if i == 0:
                    primary = arc
                else:
                    additional_arcs.append(arc)
        else:
            primary = {
                "lemma": tok["lemma"], "form": form, "start": start, "end": end,
                "tag": tok["tag"], "prob": 1.0,
            }
            if tok["tag"] in ov.ADD_TAGS:
                for extra in ov.ADD_TAGS[tok["tag"]].split(","):
                    additional_arcs.append({
                        "lemma": tok["lemma"], "form": form, "start": start, "end": end,
                        "tag": extra.strip(), "prob": -1, "additional": True,
                    })

        if word in no_disambiguate and not is_retokenizable:
            candidate = morfo_by_span.get((tok["begin"], tok["end"]))
            if candidate is not None:
                for alt in candidate.get("analysis", []):
                    if alt["tag"] == tok["tag"]:
                        continue  # this is the one FreeLing selected; already added above
                    additional_arcs.append({
                        "lemma": alt["lemma"], "form": form, "start": start, "end": end,
                        "tag": alt["tag"], "prob": alt.get("prob", -1), "additional": True,
                    })
                    if alt["tag"] in ov.ADD_TAGS:
                        for extra in ov.ADD_TAGS[alt["tag"]].split(","):
                            additional_arcs.append({
                                "lemma": alt["lemma"], "form": form, "start": start, "end": end,
                                "tag": extra.strip(), "prob": -1, "additional": True,
                            })

        # A token's own 'additional' flag means "more arcs follow at this
        # same lattice position, don't advance yet" -- true for the primary
        # whenever alternates follow it, not just for the alternates
        # themselves. Confirmed against the gold treebank's own recorded
        # lattices (build/srg/tsdb/gold): getting this wrong put every
        # <NoDisambiguate> alternative (and everything after it) one lattice
        # position late, which ACE quietly tolerated by still finding SOME
        # reading on most sentences but is simply wrong -- e.g. "La gata
        # está tranquila." lost its only reading because of it.
        primary["additional"] = bool(additional_arcs)
        tokens.append(primary)
        if additional_arcs:
            additional_arcs[-1]["last"] = True
            tokens.extend(additional_arcs)

    return tokens


def _render_pos(pos: str, conf: float) -> tuple[str, str]:
    """Build the YY lattice's lrule-list and postag-list strings for one arc.

    `pos` is plain (one tag) for almost every word, but for a retokenizable
    clitic attachment it is the glued multi-rule string from _glue(), e.g.
    'VMN0000" "+PP3MSA0' -- i.e. two rule names, "VMN0000" and "+PP3MSA0".
    srg_freeling2yy.convert_sentences reuses that one string verbatim for
    both the lrule field and the postag field, which is where it goes wrong:
    checked directly against ACE (build/DBS/SRG_1008.dat), the lrule list
    must stay bare quoted names with no numbers in between, but the postag
    list needs a probability after *every* tag -- a single trailing
    probability for two tags makes ACE silently drop the second rule
    ("lexemes do not span position N"), rather than erroring loudly.
    """
    parts = pos.split('" "')
    lrule = " ".join(f'"{p}"' for p in parts)
    conf_str = f"{conf:.8f}"
    postag = " ".join(f'"{p}" {conf_str}' for p in parts)
    return lrule, postag


def _quoted(s: str) -> str:
    """Quote a lemma/surface field, matching convert_sentences' one escape case."""
    return '"\\""' if s == '"' else f'"{s}"'


def _convert_sentence(sentence: str, tokens: list[dict], override_dicts: dict) -> str:
    """Render one sentence's token-arc list as a single YY lattice line.

    Structurally the same walk as srg_freeling2yy.convert_sentences (same
    lattice position bookkeeping, same override_tag/override_lemma calls),
    except for how a multi-rule `pos` gets rendered -- see _render_pos.
    """
    if not tokens:
        text = sentence.rstrip("\n")
        escaped = text.replace('"', '\\"')
        return f'(1,0,1, <0:{len(text)}>,1,"{escaped}" "{escaped}",0, "np00v00", "np00v00" 1.0)'.lower()

    arcs: list[str] = []
    frm = 0
    to = 1
    for num, tok in enumerate(tokens, start=1):
        is_additional = tok["additional"]
        surface = tok["form"]
        tag_prob = {"tag": tok["tag"], "prob": tok["prob"]}
        pos_conf = s2yy.override_tag(tag_prob, surface.lower(), tok["lemma"], tok["tag"], override_dicts)
        pos = pos_conf["tags"][0]
        conf = float(pos_conf["prob"])
        lemma = s2yy.override_lemma(tok["lemma"], pos, override_dicts)

        start_pos, end_pos = frm, to
        if not is_additional or tok.get("last"):
            frm += 1
            to += 1

        lrule, postag = _render_pos(pos, conf)
        arcs.append(
            f"({num}, {start_pos}, {end_pos}, <{int(tok['start'])}:{int(tok['end'])}>, 1, "
            f"{_quoted(lemma)} {_quoted(surface)}, 0, {lrule}, {postag})"
        )
    return " ".join(arcs).lower()


def main() -> None:
    """Read one sentence from stdin and print its YY lattice line."""
    sentence = sys.stdin.read().strip()
    if not sentence:
        return
    fuse, replace, no_disambiguate, _output = parse_sppp_dat.parse_sppp(str(SRG_FREELING_DAT))
    override_dicts = {"fuse": fuse, "replace": replace, "no_disambiguate": no_disambiguate}
    tokens = _build_tokens(sentence, override_dicts)
    print(_convert_sentence(sentence, tokens, override_dicts))


if __name__ == "__main__":
    main()

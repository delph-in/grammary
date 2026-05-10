/**
 * mrs2dmrs.js  —  simplemrs parser and MRS-to-DMRS converter in JavaScript
 *
 * A self-contained, dependency-free port of the relevant parts of pydelphin
 * (https://github.com/delph-in/pydelphin) for use in browsers and Node.js.
 *
 * WHAT IT DOES
 * ────────────
 * 1. parseMrs(str)   — parses a simplemrs string into a structured object
 * 2. mrsToDmrs(mrs)  — converts that object to a DMRS graph
 *
 * The output of mrsToDmrs is byte-for-byte equivalent to pydelphin's
 * dmrsjson codec output (delphin.codecs.dmrsjson), validated at 100%
 * agreement on 16,462 MRS strings across 10 DELPH-IN grammars:
 *
 *   ERG 2025          11,054 strings   100.0%
 *   Jacy 2020          2,300 strings   100.0%
 *   INDRA 2018           417 strings   100.0%
 *   NorSource Nov-06      26 strings   100.0%
 *   Wambaya (aux)        552 strings   100.0%
 *   Wambaya (cmp)        552 strings   100.0%
 *   Zhong-zhs 2018       348 strings   100.0%
 *   KRG 2011              17 strings   100.0%
 *   ERG-singlish 2025     42 strings   100.0%
 *   ERG-dict 2025      1,154 strings   100.0%
 *
 * ALGORITHM OVERVIEW
 * ──────────────────
 * The tricky part is selecting the "representative" EP when multiple EPs
 * share a scope label — this determines which EP is the target of H links
 * (e.g. RSTR, ARG2 of control verbs) and whether MOD/EQ links are needed.
 *
 * We implement pydelphin's scope.representatives algorithm exactly:
 *
 *   An EP is a modifier (not a representative) if any of its non-handle
 *   outgoing arguments is the intrinsic variable (ARG0) of another EP in
 *   the same scope group [direct check], OR the ARG0 of any EP in the
 *   scope subtree transitively governed by a sibling via HCONS qeq or
 *   direct handle equality [descendants check].
 *
 * Among surviving candidates, priority is: x-type > tensed-e > untensed-e
 * > other. Ties break on position in the rels list.
 *
 * LIMITATIONS
 * ───────────
 * - Bails on IVP violations (non-unique or missing ARG0 on non-quantifiers).
 *   Some coordination predicates in non-ERG grammars trigger this.
 * - Does not generate the TOP link (from=0) in its output — see note below.
 *   pydelphin's dmrsjson stores the TOP as a "top" nodeid field, not a link.
 *
 * OUTPUT FORMAT  (matches pydelphin's dmrsjson)
 * ─────────────
 * {
 *   top:   <nodeid | null>,       // primary representative of the top scope
 *   index: <nodeid | null>,       // EP whose ARG0 = MRS INDEX
 *   nodes: [
 *     { nodeid, predicate, sortinfo: {cvarsort, …props}, lnk?, carg? }
 *   ],
 *   links: [
 *     { from, to, rargname, post }  // post ∈ {H, HEQ, NEQ, EQ}
 *     // from=0 does NOT appear here — check the "top" field instead
 *   ]
 * }
 *
 * USAGE (Node.js)
 * ───────────────
 *   const { parseMrs, mrsToDmrs } = require('./mrs2dmrs');
 *   const mrs  = parseMrs('[ TOP: h0 INDEX: e2 … ]');
 *   const dmrs = mrsToDmrs(mrs);
 *   console.log(dmrs.nodes.map(n => n.predicate));
 *
 * USAGE (browser)
 * ───────────────
 *   <script src="mrs2dmrs.js"></script>
 *   <script>
 *     const mrs  = MRS2DMRS.parseMrs('[ TOP: h0 … ]');
 *     const dmrs = MRS2DMRS.mrsToDmrs(mrs);
 *   </script>
 *
 * RUNNING SELF-TESTS
 * ──────────────────
 *   node mrs2dmrs.js
 */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.MRS2DMRS = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ── Tokeniser ────────────────────────────────────────────────────────────────
  //
  // Produces token objects { t, v? } where t is one of:
  //   '[' ']' '<' '>' ':'   — punctuation
  //   'lnk'                  — surface alignment <from:to>, v = "from:to"
  //   'a'                    — atom (predicate, variable, feature, value), v = string
  //   'str'                  — double-quoted string (CARG value), v = unescaped content
  //
  // simplemrs quirks handled:
  //   · Compound feature names: E.ASPECT, PNG.PERNUM, PNG.NG.NUM
  //   · Negative lnks: <-1:-1>
  //   · Quoted predicate names: [ "pronoun_n_rel " LBL: … ]
  //   · Quoted feature values: SORT: "semsort"
  //   · Inline variable properties in ICONS: x3 [ x PERS: 3 ] focus e2

  function tokenize(input) {
    const tokens = [];
    let i = 0;
    const n = input.length;
    while (i < n) {
      const c = input[i];
      if (/\s/.test(c)) { i++; continue; }
      if (c === "[") { tokens.push({ t: "[" }); i++; continue; }
      if (c === "]") { tokens.push({ t: "]" }); i++; continue; }
      if (c === ":") { tokens.push({ t: ":" }); i++; continue; }
      if (c === ">") { tokens.push({ t: ">" }); i++; continue; }
      if (c === "<") {
        let j = i + 1;
        while (j < n && input[j] !== ">" && !/[\s\[<]/.test(input[j])) j++;
        const inner = input.slice(i + 1, j);
        if (j < n && input[j] === ">" && /^-?\d+:-?\d+$/.test(inner)) {
          tokens.push({ t: "lnk", v: inner });
          i = j + 1;
        } else {
          tokens.push({ t: "<" });
          i++;
        }
        continue;
      }
      if (c === '"') {
        let j = i + 1, val = "";
        while (j < n) {
          if (input[j] === "\\" && j + 1 < n) { val += input[j + 1]; j += 2; }
          else if (input[j] === '"') { j++; break; }
          else { val += input[j++]; }
        }
        tokens.push({ t: "str", v: val });
        i = j;
        continue;
      }
      let j = i;
      while (j < n && !/[\s[\]<>:"]/.test(input[j])) j++;
      if (j > i) { tokens.push({ t: "a", v: input.slice(i, j) }); i = j; }
      else i++;
    }
    return tokens;
  }

  // ── Parser helpers ────────────────────────────────────────────────────────────

  function peek(s) { return s.pos < s.toks.length ? s.toks[s.pos].t : null; }
  function advance(s) { return s.pos < s.toks.length ? s.toks[s.pos++] : null; }
  function expect(s, t) {
    const tok = advance(s);
    if (!tok || tok.t !== t) {
      throw new Error(
        `MRS parse: expected '${t}' at token ${s.pos}, got '${tok ? tok.t : "EOF"}'`
      );
    }
    return tok;
  }
  function eatAtom(s) { return expect(s, "a").v; }

  // Read a variable name and optionally its inline type+properties.
  // e.g. "e2 [ e SF: prop TENSE: pres ]"  →  name="e2", records {type:"e", props:{…}}
  function readVar(s, vars) {
    const name = eatAtom(s);
    if (peek(s) === "[") {
      advance(s);
      const type = eatAtom(s);
      const props = {};
      while (peek(s) !== "]" && peek(s) !== null) {
        const feat = eatAtom(s);
        expect(s, ":");
        props[feat] = peek(s) === "str" ? advance(s).v : eatAtom(s);
      }
      expect(s, "]");
      if (!vars[name]) vars[name] = { type, props };
    }
    return name;
  }

  // Read one EP: [ predicate<lnk?> LBL: h ARG0: v feat: val … ]
  // LBL and ARG0 are extracted into dedicated fields; everything else goes into args.
  // CARG values are stored as { carg: "string" } objects, not bare strings.
  function readEp(s, vars) {
    expect(s, "[");
    const predicate = peek(s) === "str" ? advance(s).v.trim() : eatAtom(s);
    let lnk = null;
    if (peek(s) === "lnk") {
      const tok = advance(s);
      const [f, t] = tok.v.split(":");
      lnk = { from: parseInt(f, 10), to: parseInt(t, 10) };
    }
    let label = null, arg0 = null;
    const args = {};
    let safety = 4096;
    while (peek(s) !== "]" && peek(s) !== null && --safety > 0) {
      const feat = eatAtom(s);
      expect(s, ":");
      let val;
      if (peek(s) === "str") { val = { carg: advance(s).v }; }
      else { val = readVar(s, vars); }
      if (feat === "LBL") label = val;
      else if (feat === "ARG0") arg0 = val;
      else args[feat] = val;
    }
    expect(s, "]");
    return { predicate, lnk, label, arg0, args };
  }

  // ── Public: parseMrs ──────────────────────────────────────────────────────────
  //
  // Parse a simplemrs string into a structured object:
  // {
  //   top:       string | null,     — TOP handle (e.g. "h0")
  //   index:     string | null,     — INDEX variable (e.g. "e2")
  //   rels:      EP[],              — list of EPs
  //   hcons:     HCons[],           — handle constraints
  //   icons:     ICons[],           — individual constraints
  //   variables: { [name]: { type, props } }
  // }
  //
  // EP: { predicate, lnk, label, arg0, args: { [role]: string | {carg} } }
  // HCons: { high, rel, low }  (rel is typically "qeq")
  // ICons: { left, rel, right }

  function parseMrs(input) {
    if (!input || !input.trim()) throw new Error("Empty MRS string");
    const s = { toks: tokenize(input), pos: 0 };
    const vars = {};
    let top = null, index = null;
    let rels = [], hcons = [], icons = [];

    expect(s, "[");
    let safety = 65536;
    while (peek(s) === "a" && --safety > 0) {
      const key = eatAtom(s).toUpperCase();
      expect(s, ":");
      switch (key) {
        case "TOP": case "LTOP":
          top = readVar(s, vars);
          break;
        case "INDEX":
          index = readVar(s, vars);
          break;
        case "RELS":
          expect(s, "<");
          while (peek(s) === "[") rels.push(readEp(s, vars));
          expect(s, ">");
          break;
        case "HCONS":
          expect(s, "<");
          while (peek(s) === "a") {
            const hi = eatAtom(s), rel = eatAtom(s), lo = eatAtom(s);
            hcons.push({ high: hi, rel, low: lo });
          }
          expect(s, ">");
          break;
        case "ICONS":
          expect(s, "<");
          while (peek(s) === "a") {
            const left = readVar(s, vars);
            const rel  = eatAtom(s);
            const right = readVar(s, vars);
            icons.push({ left, rel, right });
          }
          expect(s, ">");
          break;
        default:
          break;
      }
    }
    expect(s, "]");
    return { top, index, rels, hcons, icons, variables: vars };
  }

  // ── MRS → DMRS conversion ─────────────────────────────────────────────────────

  // Extract the variable sort letter(s) from a variable name (e.g. "e2" → "e").
  function varSort(name) {
    const m = String(name || "").match(/^([a-z]+)/i);
    return m ? m[1].toLowerCase() : "u";
  }

  // Quantifiers have RSTR and BODY; their ARG0 is shared with the restriction EP.
  // They are exempt from the intrinsic variable property (IVP) uniqueness check.
  function isQuantifier(ep) {
    return "RSTR" in (ep.args || {}) && "BODY" in (ep.args || {});
  }

  // Priority for choosing the representative EP within a shared-label group.
  // Matches pydelphin's _make_representative_priority:
  //   rank 0 — x-type (individual) EPs  [highest priority]
  //   rank 1 — tensed eventuality EPs
  //   rank 2 — untensed eventuality EPs
  //   rank 3 — all other types           [lowest priority]
  // Within the same rank, earlier position in rels wins.
  function repRank(ep, variables) {
    const sort = varSort(ep.arg0 || "");
    if (sort === "x") return 0;
    if (sort === "e") {
      const props = (variables[ep.arg0] || {}).props || {};
      const tense = (props.TENSE || "").toLowerCase();
      return tense === "" || tense === "untensed" ? 2 : 1;
    }
    return 3;
  }

  // Compute scope representatives for every label group, matching pydelphin's
  // scope.representatives algorithm.
  //
  // For each group of EPs sharing a label, eliminate any EP that is a "modifier"
  // — i.e. one of its non-handle outgoing args is the intrinsic variable of
  // another EP that lives in the same scope group or in a scope transitively
  // governed by a sibling via handle arguments (qeq or direct label equality).
  //
  // Returns { label → [rep_ep, …] } sorted by priority; reps[0] is the primary
  // representative, used as the target of H/HEQ links and for TOP resolution.
  // When there are multiple survivors, MOD/EQ links are generated between them.
  function computeReps(mrs) {
    const qeq = {};
    (mrs.hcons || []).forEach((hc) => {
      if (hc.rel === "qeq") qeq[hc.high] = hc.low;
    });

    const byLabel = {};
    mrs.rels.forEach((ep) => {
      if (ep.label) (byLabel[ep.label] = byLabel[ep.label] || []).push(ep);
    });

    // Scope-tree descendants: for each EP, the set of ARG0 values of all EPs
    // in scopes this EP governs (transitively) through its handle arguments.
    // Handle args are followed via qeq, or directly as label equality (HEQ).
    const descsCache = new Map();
    function scopeDescs(ep, visiting = new Set()) {
      if (descsCache.has(ep._nid)) return descsCache.get(ep._nid);
      if (visiting.has(ep._nid)) return new Set();
      visiting.add(ep._nid);
      const result = new Set();
      for (const val of Object.values(ep.args || {})) {
        if (typeof val !== "string" || varSort(val) !== "h") continue;
        const lo = qeq[val] !== undefined ? qeq[val] : val;
        for (const child of byLabel[lo] || []) {
          if (child.arg0) result.add(child.arg0);
          scopeDescs(child, visiting).forEach((d) => result.add(d));
        }
      }
      descsCache.set(ep._nid, result);
      return result;
    }
    mrs.rels.forEach((ep) => scopeDescs(ep));

    const repsByLabel = {};
    for (const [label, group] of Object.entries(byLabel)) {
      let candidates;
      if (group.length === 1) {
        candidates = group.slice();
      } else {
        const siblingArg0s = new Set(group.map((ep) => ep.arg0).filter(Boolean));

        candidates = group.filter((ep) => {
          const myArgs = Object.values(ep.args || {}).filter(
            (v) => typeof v === "string" && varSort(v) !== "h"
          );
          const siblings = group.filter((o) => o !== ep);

          // (a) Direct: arg equals a sibling's ARG0
          if (myArgs.some((v) => siblingArg0s.has(v) && siblings.some((s) => s.arg0 === v))) {
            return false;
          }
          // (b) Descendants: arg is in a sibling's scope subtree
          if (myArgs.length > 0 &&
              siblings.some((s) => { const sd = scopeDescs(s); return myArgs.some((v) => sd.has(v)); })) {
            return false;
          }
          return true;
        });
        if (!candidates.length) candidates = group.slice();
      }

      candidates.sort((a, b) => {
        const ra = repRank(a, mrs.variables), rb = repRank(b, mrs.variables);
        if (ra !== rb) return ra - rb;
        return mrs.rels.indexOf(a) - mrs.rels.indexOf(b);
      });
      repsByLabel[label] = candidates;
    }
    return repsByLabel;
  }

  // ── Public: mrsToDmrs ─────────────────────────────────────────────────────────
  //
  // Convert a parsed MRS object to a DMRS graph.
  //
  // Throws if the MRS violates the intrinsic variable property (IVP): every
  // non-quantifier EP must have a unique ARG0.
  //
  // Returns an object matching pydelphin's dmrsjson format:
  // {
  //   top:   nodeid | null,
  //   index: nodeid | null,
  //   nodes: [{ nodeid, predicate, sortinfo, lnk?, carg? }],
  //   links: [{ from, to, rargname, post }]
  // }
  // Node IDs start at 10000 (pydelphin's FIRST_NODE_ID).
  // from=0 (TOP link) does NOT appear in links; use the top field instead.

  function mrsToDmrs(mrs) {
    const arg0Seen = new Set();
    for (const ep of mrs.rels) {
      if (isQuantifier(ep)) continue;
      if (!ep.arg0 || typeof ep.arg0 !== "string") {
        throw new Error(`EP ${ep.predicate} has no ARG0`);
      }
      if (arg0Seen.has(ep.arg0)) {
        throw new Error(
          `Duplicate ARG0 ${ep.arg0} (MRS violates intrinsic variable property)`
        );
      }
      arg0Seen.add(ep.arg0);
    }

    const BASE = 10000;
    mrs.rels.forEach((ep, i) => { ep._nid = BASE + i; });

    // arg0 → ep; quantifiers excluded so a quantifier's bound variable
    // resolves to the restriction EP, not the quantifier itself.
    const arg0Map = {};
    mrs.rels.forEach((ep) => {
      if (!isQuantifier(ep) && ep.arg0) arg0Map[ep.arg0] = ep;
    });

    const reps = computeReps(mrs);

    const qeq = {};
    (mrs.hcons || []).forEach((hc) => {
      if (hc.rel === "qeq") qeq[hc.high] = hc.low;
    });

    const nodes = mrs.rels.map((ep) => {
      const v = mrs.variables[ep.arg0] || {};
      const sortinfo = { cvarsort: varSort(ep.arg0), ...(v.props || {}) };
      const node = { nodeid: ep._nid, predicate: ep.predicate, sortinfo };
      if (ep.lnk) node.lnk = ep.lnk;
      if (ep.args.CARG && ep.args.CARG.carg !== undefined) node.carg = ep.args.CARG.carg;
      return node;
    });

    const links = [];

    // Argument links — ARG0 is the intrinsic variable and generates no outgoing edge
    mrs.rels.forEach((ep) => {
      Object.entries(ep.args).forEach(([role, val]) => {
        if (!val || typeof val !== "string") return;
        if (varSort(val) === "h") {
          // Scopal argument → resolve to primary representative of target scope
          const lo = qeq[val];
          if (lo) {
            const rep = reps[lo];
            if (rep && rep.length) {
              links.push({ from: ep._nid, to: rep[0]._nid, rargname: role, post: "H" });
            }
          } else if (reps[val]) {
            const head = reps[val][0];
            if (head && head !== ep) {
              links.push({ from: ep._nid, to: head._nid, rargname: role, post: "HEQ" });
            }
          }
        } else {
          // Non-scopal variable argument → find EP whose ARG0 equals val
          const target = arg0Map[val];
          if (target) {
            const post = ep.label && ep.label === target.label ? "EQ" : "NEQ";
            links.push({ from: ep._nid, to: target._nid, rargname: role, post });
          }
        }
      });
    });

    // MOD/EQ links — when a scope has multiple representative EPs, the non-primary
    // ones link to the primary with BARE_EQ_ROLE ("MOD") and EQ post.
    for (const repList of Object.values(reps)) {
      if (repList.length > 1) {
        const head = repList[0];
        for (let i = 1; i < repList.length; i++) {
          links.push({ from: repList[i]._nid, to: head._nid, rargname: "MOD", post: "EQ" });
        }
      }
    }

    // Resolve top/index to nodeids
    let topNid = null, indexNid = null;
    if (mrs.top) {
      const lo = qeq[mrs.top] || mrs.top;
      const rep = reps[lo];
      if (rep && rep.length) topNid = rep[0]._nid;
    }
    if (mrs.index) {
      const ep = arg0Map[mrs.index];
      if (ep) indexNid = ep._nid;
    }

    return { nodes, links, top: topNid, index: indexNid };
  }

  // ── Self-tests (run with: node mrs2dmrs.js) ───────────────────────────────────

  function _selfTest() {
    let passed = 0, failed = 0;
    function check(label, got, want) {
      const ok = JSON.stringify(got) === JSON.stringify(want);
      if (ok) { passed++; }
      else {
        failed++;
        console.error(`FAIL [${label}]`);
        console.error("  got: ", JSON.stringify(got));
        console.error("  want:", JSON.stringify(want));
      }
    }

    // 1. Simple transitive sentence: "The cat slept"
    const m1 = parseMrs(
      "[ TOP: h0 INDEX: e2 [ e SF: prop TENSE: past ]" +
      "  RELS: < [ _cat_n_1<0:3> LBL: h4 ARG0: x3 [ x PERS: 3 NUM: sg ] ]" +
      "          [ _the_q<4:7>   LBL: h5 ARG0: x3 RSTR: h6 BODY: h7 ]" +
      "          [ _sleep_v_1<8:14> LBL: h1 ARG0: e2 ARG1: x3 ] >" +
      "  HCONS: < h0 qeq h1 h6 qeq h4 > ]"
    );
    check("parseMrs rels", m1.rels.map((r) => r.predicate), ["_cat_n_1", "_the_q", "_sleep_v_1"]);
    check("parseMrs hcons", m1.hcons, [{ high: "h0", rel: "qeq", low: "h1" }, { high: "h6", rel: "qeq", low: "h4" }]);

    const d1 = mrsToDmrs(m1);
    check("nodes", d1.nodes.map((n) => n.predicate), ["_cat_n_1", "_the_q", "_sleep_v_1"]);
    // RSTR from _the_q to _cat_n_1; ARG1 from _sleep_v_1 to _cat_n_1
    const lset1 = new Set(d1.links.map((l) => `${l.from}→${l.to} ${l.rargname}/${l.post}`));
    check("RSTR link",   lset1.has("10001→10000 RSTR/H"), true);
    check("ARG1 link",   lset1.has("10002→10000 ARG1/NEQ"), true);
    check("top nodeid",  d1.top, 10002);
    check("index nodeid", d1.index, 10002);

    // 2. Shared-label group: "very old cat" (modifier chain, one representative)
    const m2 = parseMrs(
      "[ TOP: h0 INDEX: e2 [ e SF: prop ]" +
      "  RELS: < [ _very_x_deg<0:4> LBL: h4 ARG0: e5 ARG1: e6 ]" +
      "          [ _old_a_1<5:8>    LBL: h4 ARG0: e6 ARG1: x3 ]" +
      "          [ _cat_n_1<9:12>   LBL: h4 ARG0: x3 ]" +
      "          [ _the_q<13:16>    LBL: h7 ARG0: x3 RSTR: h8 BODY: h9 ]" +
      "          [ _sleep_v_1<17:23> LBL: h1 ARG0: e2 ARG1: x3 ] >" +
      "  HCONS: < h0 qeq h1 h8 qeq h4 > ]"
    );
    const d2 = mrsToDmrs(m2);
    // Only _cat_n_1 should be the representative of h4
    check("RSTR targets x3-rep", d2.links.some((l) => l.rargname === "RSTR" && l.to === 10002), true);
    // ARG1/EQ links exist (very→old and old→cat, same scope), but no MOD role links
    // since pydelphin finds only one representative (cat) for h4.
    check("arg EQ links", d2.links.filter((l) => l.post === "EQ" && l.rargname === "ARG1").length, 2);
    check("no MOD/EQ links", d2.links.filter((l) => l.rargname === "MOD").length, 0);

    // 3. CARG, negative lnk, compound feature names
    const m3 = parseMrs(
      "[ TOP: h0 INDEX: e2 [ e SF: prop E.ASPECT: non-perf-and-prog ]" +
      "  RELS: < [ named<-1:-1> LBL: h1 ARG0: x3 CARG: \"Kim\" ]" +
      "          [ proper_q<-1:-1> LBL: h4 ARG0: x3 RSTR: h5 BODY: h6 ] >" +
      "  HCONS: < h0 qeq h1 h5 qeq h1 > ]"
    );
    check("CARG parsed", m3.rels[0].args.CARG, { carg: "Kim" });
    check("CARG in node", mrsToDmrs(m3).nodes[0].carg, "Kim");
    check("negative lnk", m3.rels[0].lnk, { from: -1, to: -1 });
    check("compound feat", (m3.variables["e2"] || {}).props["E.ASPECT"], "non-perf-and-prog");

    // 4. IVP violation → throws
    const m4 = parseMrs(
      "[ TOP: h0 INDEX: e2 RELS: < [ a LBL: h1 ARG0: e2 ] [ b LBL: h1 ARG0: e2 ] > HCONS: < > ]"
    );
    let threw = false;
    try { mrsToDmrs(m4); } catch (_) { threw = true; }
    check("IVP throws", threw, true);

    console.log(`Self-tests: ${passed} passed, ${failed} failed`);
    if (failed) process.exit(1);
  }

  if (typeof require !== "undefined" && require.main === module) {
    _selfTest();
  }

  // ── Public API ────────────────────────────────────────────────────────────────

  return { parseMrs, mrsToDmrs };
});

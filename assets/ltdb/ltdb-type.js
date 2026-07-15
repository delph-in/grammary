(function () {
  const dbCache = new Map();
  const scriptUrl = document.currentScript
    ? document.currentScript.src
    : window.location.href;
  let sqlPromise = null;

  function getSql() {
    if (!sqlPromise) {
      if (!window.initSqlJs) {
        return Promise.reject(new Error("SQLite WASM loader is unavailable"));
      }
      sqlPromise = window.initSqlJs({
        locateFile: (file) => new URL(file, scriptUrl).href,
      });
    }
    return sqlPromise;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function typeHref(grammar, typ) {
    const params = new URLSearchParams({ grammar, type: typ });
    return `type.html?${params.toString()}`;
  }

  function splitTypes(value) {
    return String(value || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
  }

  function typeLinks(grammar, value, limit) {
    const types = splitTypes(value);
    const shown = typeof limit === "number" ? types.slice(0, limit) : types;
    const links = shown
      .map((typ) => `<a href="${typeHref(grammar, typ)}">${escapeHtml(typ)}</a>`)
      .join(", ");
    if (typeof limit === "number" && types.length > limit) {
      return `${links} (and ${types.length - limit} more)`;
    }
    return links;
  }

  function linkTdl(grammar, tdl) {
    const escaped = escapeHtml(tdl || "");
    return escaped.replace(
      /\b[A-Za-z0-9_*+?.$~^@!:-]+(?=\s*(?::=|&|\.|,|\]|>|\)|$))/g,
      (typ) => `<a href="${typeHref(grammar, typ)}">${typ}</a>`
    );
  }

  async function fetchDbBytes(url) {
    const gzUrl = url + ".gz";
    const gzResponse = await fetch(gzUrl);
    if (gzResponse.ok) {
      if (typeof DecompressionStream === "undefined") {
        throw new Error("Browser does not support DecompressionStream; cannot load compressed DB");
      }
      const stream = gzResponse.body.pipeThrough(new DecompressionStream("gzip"));
      return new Uint8Array(await new Response(stream).arrayBuffer());
    }
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Could not fetch grammar DB: ${response.status}`);
    }
    return new Uint8Array(await response.arrayBuffer());
  }

  async function loadDb(grammar) {
    if (dbCache.has(grammar)) {
      return dbCache.get(grammar);
    }
    const SQL = await getSql();
    const db = new SQL.Database(
      await fetchDbBytes(`db/${encodeURIComponent(grammar)}.grammar.sqlite`)
    );
    dbCache.set(grammar, db);
    return db;
  }

  function getObject(db, sql, params) {
    const stmt = db.prepare(sql);
    stmt.bind(params || []);
    const row = stmt.step() ? stmt.getAsObject() : null;
    stmt.free();
    return row;
  }

  function getAll(db, sql, params) {
    const stmt = db.prepare(sql);
    stmt.bind(params || []);
    const rows = [];
    while (stmt.step()) {
      rows.push(stmt.getAsObject());
    }
    stmt.free();
    return rows;
  }

  function renderWords(rows) {
    if (!rows.length) return "";
    const body = rows
      .map((row) => {
        const words = JSON.parse(row.words_json || "[]")
          .map((item) => `<i>${escapeHtml(item.word)}</i> (${escapeHtml(item.freq)})`)
          .join(" ");
        return `<tr>
          <td>${escapeHtml(row.orth || row.lexid || "")}</td>
          <td>${escapeHtml(row.freq || 0)}</td>
          <td>${words}</td>
        </tr>`;
      })
      .join("");
    return `<h3>Words</h3>
      <table class="table table-hover table-borderless table-sm">
        <thead class="thead-light"><tr><th>Lexeme</th><th>Freq</th><th>Words</th></tr></thead>
        <tbody>${body}</tbody>
      </table>`;
  }

  function renderType(container, grammar, typ, info, words) {
    if (!info) {
      container.innerHTML = `<h1>"${escapeHtml(typ)}" not found in this grammar</h1>`;
      return;
    }
    const parents = info.parents
      ? `<li>Parents: ${typeLinks(grammar, info.parents)}</li>`
      : "";
    const children = info.children
      ? `<li>Children: ${typeLinks(grammar, info.children, 10)}</li>`
      : "";
    const desc = info.docstring || info.description || "";
    const examples = info.status !== "lex-entry" && info.status !== "generic-lex-entry"
      ? `<section id="examples"
           class="ltdb-examples"
           data-grammar="${escapeHtml(grammar)}"
           data-type="${escapeHtml(typ)}"
           data-db="db/${escapeHtml(grammar)}.examples.sqlite">
           <h3>Sentences</h3>
           <p class="text-muted">Loading examples...</p>
         </section>`
      : "";

    container.innerHTML = `
      <h1>${escapeHtml(typ)} (${escapeHtml(info.status)})</h1>
      ${desc ? `<p>${escapeHtml(desc)}</p>` : ""}
      <ul>${parents}${children}</ul>
      ${renderWords(words)}
      ${examples}
      <h3>TDL</h3>
      <pre class="highlight">${linkTdl(grammar, info.tdl || "")}</pre>
      <p>${escapeHtml(info.src || "")}${info.line ? `, ${escapeHtml(info.line)}` : ""}</p>
    `;

    const examplesContainer = container.querySelector(".ltdb-examples");
    if (examplesContainer && window.LTDBExamples) {
      window.LTDBExamples.hydrate(examplesContainer);
    }
  }

  async function main() {
    const container = document.querySelector("[data-ltdb-type-shell]");
    if (!container) return;
    const params = new URLSearchParams(window.location.search);
    const grammar = params.get("grammar") || container.dataset.defaultGrammar || "";
    const typ = params.get("type") || "";
    if (!grammar || !typ) {
      container.innerHTML = '<p class="text-muted">No grammar or type selected.</p>';
      return;
    }
    document.querySelectorAll("[data-ltdb-grammar-link]").forEach((link) => {
      link.href = `${grammar}/${link.dataset.ltdbGrammarLink}.html`;
    });
    try {
      const db = await loadDb(grammar);
      const info = getObject(db, "SELECT * FROM types WHERE typ = ? LIMIT 1", [typ]);
      const words = info && info.status === "lex-type"
        ? getAll(
            db,
            "SELECT * FROM lex_type_words WHERE typ = ? ORDER BY rank",
            [typ]
          )
        : [];
      renderType(container, grammar, typ, info, words);
      document.title = `${typ} - ${grammar} - LTDB Static Mirror`;
    } catch (error) {
      container.innerHTML = `<h1>Type unavailable</h1>
        <p class="text-muted">${escapeHtml(error.message)}</p>`;
    }
  }

  document.addEventListener("DOMContentLoaded", main);

  window.LTDBType = {
    typeHref,
    linkTdl,
  };
})();

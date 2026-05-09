(function () {
  const dbCache = new Map();
  const scriptUrl = document.currentScript
    ? document.currentScript.src
    : window.location.href;

  let _sqlPromise = null;
  function getSql() {
    if (!_sqlPromise) {
      if (!window.initSqlJs) {
        return Promise.reject(new Error("SQLite WASM loader is unavailable"));
      }
      _sqlPromise = window.initSqlJs({
        locateFile: (file) => new URL(file, scriptUrl).href,
      });
    }
    return _sqlPromise;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function isHighlighted(wid, spans) {
    return spans.some(([from, to]) => wid >= from && wid < to);
  }

  function renderTokens(tokens, spans) {
    return tokens
      .map((token) => {
        const word = escapeHtml(token.word);
        if (isHighlighted(token.wid, spans)) {
          return `<span class="text-success">${word}</span>`;
        }
        return word;
      })
      .join(" ");
  }

  async function loadDb(grammar, dbUrl) {
    if (dbCache.has(grammar)) {
      return dbCache.get(grammar);
    }
    const SQL = await getSql();
    const response = await fetch(dbUrl);
    if (!response.ok) {
      throw new Error(`Could not fetch examples DB: ${response.status}`);
    }
    const bytes = new Uint8Array(await response.arrayBuffer());
    const db = new SQL.Database(bytes);
    dbCache.set(grammar, db);
    return db;
  }

  function queryExamples(db, typ) {
    const stmt = db.prepare(`
      SELECT te.rank, te.spans_json, te.source,
             e.profile, e.sid, e.sentence, e.tokens_json, e.deriv, e.mrs
      FROM type_examples AS te
      JOIN examples AS e ON te.example_id = e.example_id
      WHERE te.typ = ?
      ORDER BY te.rank
    `);
    const rows = [];
    stmt.bind([typ]);
    while (stmt.step()) {
      rows.push(stmt.getAsObject());
    }
    stmt.free();
    return rows;
  }

  function renderExamples(container, rows) {
    if (!rows.length) {
      container.innerHTML = `
        <h3>Sentences</h3>
        <p class="text-muted">No examples available in the static mirror.</p>
      `;
      return;
    }
    const items = rows
      .map((row) => {
        const tokens = JSON.parse(row.tokens_json || "[]");
        const spans = JSON.parse(row.spans_json || "[]");
        const sentence = tokens.length
          ? renderTokens(tokens, spans)
          : escapeHtml(row.sentence || "");
        const source = row.source
          ? `<small class="text-muted"> ${escapeHtml(row.source)}</small>`
          : "";
        const mrs = row.mrs
          ? `<details class="mt-2"><summary>MRS</summary><pre>${escapeHtml(
              row.mrs
            )}</pre></details>`
          : "";
        const deriv = row.deriv
          ? `<details class="mt-2"><summary>Tree</summary><pre>${escapeHtml(
              row.deriv
            )}</pre></details>`
          : "";
        return `
          <li>
            <div><a title="${escapeHtml(row.profile)}, ${row.sid}">🗩</a>
              ${sentence}${source}
            </div>
            ${mrs}
            ${deriv}
          </li>
        `;
      })
      .join("");
    container.innerHTML = `<h3>Sentences <small>(${rows.length})</small></h3><ul>${items}</ul>`;
  }

  async function hydrate(container) {
    const grammar = container.dataset.grammar;
    const typ = container.dataset.type;
    const dbUrl = container.dataset.db;
    try {
      const db = await loadDb(grammar, dbUrl);
      renderExamples(container, queryExamples(db, typ));
    } catch (error) {
      container.innerHTML = `
        <h3>Sentences</h3>
        <p class="text-muted">Examples are unavailable: ${escapeHtml(
          error.message
        )}</p>
      `;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".ltdb-examples").forEach((container) => {
      hydrate(container);
    });
  });
})();

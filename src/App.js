import { useState } from "react";
import mammoth from "mammoth";
import "./App.css";

const IMPACT_STYLE = {
  High:   { bg: "#fef2f2", color: "#b91c1c", dot: "#ef4444" },
  Medium: { bg: "#fffbeb", color: "#92400e", dot: "#f59e0b" },
  Low:    { bg: "#f0fdf4", color: "#15803d", dot: "#22c55e" },
};

const STAT_CHIPS = [
  { label: "Added",     dot: "#22c55e", bg: "rgba(34,197,94,0.12)",   color: "#4ade80", key: "added"   },
  { label: "Removed",   dot: "#ef4444", bg: "rgba(239,68,68,0.12)",   color: "#f87171", key: "removed" },
  { label: "Unchanged", dot: "#94a3b8", bg: "rgba(148,163,184,0.12)", color: "#94a3b8", key: "same"    },
];

const PANELS = [
  { side: "old", label: "Old Document", headerBg: "#fef2f2", headerColor: "#b91c1c", accent: "#fca5a5" },
  { side: "new", label: "New Document", headerBg: "#f0fdf4", headerColor: "#15803d", accent: "#86efac" },
];

const TABS = [
  { id: "compare", label: "Side by Side", icon: "⊞" },
  { id: "diff",    label: "Line Diff",    icon: "≠" },
  { id: "ai",      label: "AI Analysis",  icon: "✦" },
];

function DiffLine({ line, type }) {
  const prefix = type === "added" ? "+" : type === "removed" ? "−" : " ";
  return (
    <div className={`diff-line diff-line--${type}`}>
      <span className={`diff-gutter diff-gutter--${type}`}>{prefix}</span>
      <span className="diff-content">{line || " "}</span>
    </div>
  );
}

function computeDiff(oldText, newText) {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const m = oldLines.length, n = newLines.length;

  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = oldLines[i - 1] === newLines[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1]);

  const result = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      result.unshift({ line: oldLines[i - 1], type: "same" });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ line: newLines[j - 1], type: "added" });
      j--;
    } else {
      result.unshift({ line: oldLines[i - 1], type: "removed" });
      i--;
    }
  }

  const stats = { added: 0, removed: 0, same: 0 };
  result.forEach(r => stats[r.type]++);
  return { result, stats };
}

export default function App() {
  const [tab, setTab]               = useState("compare");
  const [oldDoc, setOldDoc]         = useState("");
  const [newDoc, setNewDoc]         = useState("");
  const [oldFileName, setOldFileName] = useState("");
  const [newFileName, setNewFileName] = useState("");
  const [aiReport, setAiReport]     = useState(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");
  const [progress, setProgress]     = useState("");

  const { result: diffLines, stats } = computeDiff(oldDoc, newDoc);

  const docState = {
    old: { doc: oldDoc, setDoc: setOldDoc, fileName: oldFileName, setFileName: setOldFileName },
    new: { doc: newDoc, setDoc: setNewDoc, fileName: newFileName, setFileName: setNewFileName },
  };

  const processFile = async (side, file) => {
    if (!file) return;
    const { setDoc, setFileName } = docState[side];
    setFileName(file.name);
    if (file.name.endsWith(".docx")) {
      const buffer = await file.arrayBuffer();
      const { value } = await mammoth.extractRawText({ arrayBuffer: buffer });
      setDoc(value);
    } else {
      const reader = new FileReader();
      reader.onload = ev => setDoc(ev.target.result);
      reader.readAsText(file);
    }
  };

  const handleFileInput = (side, e) => processFile(side, e.target.files[0]);
  const handleDrop      = (side, e) => { e.preventDefault(); processFile(side, e.dataTransfer.files[0]); };

  const runAIComparison = async () => {
    const apiKey = process.env.REACT_APP_OPENAI_KEY;
    if (!apiKey) {
      setError("API key not found. Set REACT_APP_OPENAI_KEY in your .env and restart the dev server.");
      return;
    }
    setLoading(true); setError(""); setAiReport(null);
    setProgress("Sending documents to OpenAI...");
    try {
      const res = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${apiKey}` },
        body: JSON.stringify({
          model: "gpt-4o",
          max_tokens: 1200,
          messages: [
            {
              role: "system",
              content: "You are a document analyst. Always respond with valid JSON only. No markdown, no extra text.",
            },
            {
              role: "user",
              content: `Compare these two documents and return ONLY valid JSON.\n\nOLD:\n${oldDoc.slice(0, 3000)}\n\nNEW:\n${newDoc.slice(0, 3000)}\n\nReturn ONLY:\n{"summary":"...","impact":"High|Medium|Low","new_sections":[],"removed_sections":[],"modified_fields":[{"field":"","old":"","new":"","reason":""}],"new_fields":[],"compliance_notes":"...","recommended_action":"..."}`,
            },
          ],
        }),
      });
      setProgress("Parsing response...");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error?.message || `HTTP ${res.status}`);
      const raw = data.choices?.[0]?.message?.content?.replace(/```json|```/g, "").trim();
      setAiReport(JSON.parse(raw));
      setTab("ai");
    } catch (e) {
      setError("AI analysis failed: " + e.message);
    }
    setLoading(false); setProgress("");
  };

  return (
    <div className="app">

      {/* ── HEADER ── */}
      <header className="header">
        <div className="brand">
          <div className="brand-icon">⚕</div>
          <div>
            <div className="brand-title">Novologix</div>
            <div className="brand-sub">Dummy &nbsp;·&nbsp; v1.2 → v2.0</div>
          </div>
        </div>

        <div className="stats">
          {STAT_CHIPS.map(s => (
            <div key={s.label} className="stat-chip"
              style={{ background: s.bg, border: `1px solid ${s.dot}22` }}>
              <div className="stat-dot" style={{ background: s.dot, boxShadow: `0 0 6px ${s.dot}` }} />
              <span className="stat-value" style={{ color: s.color }}>{stats[s.key]}</span>
              <span className="stat-label" style={{ color: s.color }}>{s.label}</span>
            </div>
          ))}
        </div>

        <div className="actions">
          {[
            ["old", "Old Doc", oldFileName],
            ["new", "New Doc", newFileName],
          ].map(([side, label, fname]) => (
            <label key={side} className={`upload-btn ${fname ? "upload-btn--loaded" : "upload-btn--empty"}`}>
              <span>📂</span>
              <span className="upload-btn-name">{fname || label}</span>
              <input type="file" accept=".txt,.docx" style={{ display: "none" }}
                onChange={e => handleFileInput(side, e)} />
            </label>
          ))}

          <button
            onClick={runAIComparison}
            disabled={loading}
            className={`ai-btn ${loading ? "ai-btn--loading" : "ai-btn--active"}`}
          >
            {loading
              ? <><span className="spin-icon">⏳</span> {progress}</>
              : <><span>✦</span> Run AI Analysis</>
            }
          </button>
        </div>
      </header>

      {/* ── TAB BAR ── */}
      <div className="tab-bar">
        {TABS.map(({ id, label, icon }) => {
          const active = tab === id;
          return (
            <button key={id} onClick={() => setTab(id)}
              className={`tab-btn ${active ? "tab-btn--active" : "tab-btn--inactive"}`}>
              <span style={{ fontSize: 14, opacity: active ? 1 : 0.6 }}>{icon}</span>
              {label}
              {id === "ai" && aiReport && <span className="tab-done-badge">Done</span>}
            </button>
          );
        })}
      </div>

      {/* ── CONTENT ── */}
      <div className="content">

        {/* SIDE BY SIDE + LINE DIFF */}
        {tab === "compare" && (
          <div className="compare-grid">
            {PANELS.map(({ side, label, headerBg, headerColor, accent }) => {
              const { doc, setDoc, fileName } = docState[side];
              return (
                <div key={side} className="panel">
                  <div className="panel-header"
                    style={{ background: headerBg, color: headerColor, borderBottom: `2px solid ${accent}` }}>
                    <span className="panel-dot" style={{ background: headerColor }} />
                    {fileName || label}
                  </div>

                  {!doc ? (
                    <label className="drop-zone"
                      onDragOver={e => e.preventDefault()}
                      onDrop={e => handleDrop(side, e)}>
                      <div className="drop-zone-icon"
                        style={{ background: headerBg, border: `2px solid ${accent}` }}>📄</div>
                      <div>
                        <div className="drop-zone-title">Drop file here</div>
                        <div className="drop-zone-hint">or click to browse &nbsp;·&nbsp; .txt or .docx</div>
                      </div>
                      <input type="file" accept=".txt,.docx" style={{ display: "none" }}
                        onChange={e => handleFileInput(side, e)} />
                    </label>
                  ) : (
                    <textarea className="doc-textarea"
                      value={doc}
                      onChange={e => setDoc(e.target.value)}
                      spellCheck={false}
                    />
                  )}
                </div>
              );
            })}

            {/* Third panel: Line Diff */}
            <div className="panel">
              <div className="panel-header"
                style={{ background: "#f8fafc", color: "#475569", borderBottom: "2px solid #94a3b8" }}>
                <span className="panel-dot" style={{ background: "#475569" }} />
                Line Diff
                <span className="diff-inline-count">{stats.added + stats.removed} changed</span>
              </div>
              <div className="diff-panel-inner">
                {(!oldDoc && !newDoc) ? (
                  <div className="diff-empty">
                    <div className="diff-empty-icon">≠</div>
                    <div className="diff-empty-text">Load both documents to see line-by-line diff</div>
                  </div>
                ) : (
                  <>
                    <div className="diff-inline-legend">
                      <span><span className="diff-legend-dot" style={{ background: "#22c55e" }} />Added</span>
                      <span><span className="diff-legend-dot" style={{ background: "#ef4444" }} />Removed</span>
                    </div>
                    {diffLines
                      .filter(d => d.type !== "same" || d.line.trim())
                      .map((d, i) => <DiffLine key={i} line={d.line} type={d.type} />)}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* LINE DIFF */}
        {tab === "diff" && (
          <div className="diff-view">
            <div className="diff-legend">
              <span className="diff-legend-title">Line Diff</span>
              <span>
                <span className="diff-legend-dot" style={{ background: "#22c55e" }} />
                Added in new doc
              </span>
              <span>
                <span className="diff-legend-dot" style={{ background: "#ef4444" }} />
                Removed from old doc
              </span>
              <span className="diff-legend-count">{stats.added + stats.removed} changed lines</span>
            </div>
            <div>
              {diffLines
                .filter(d => d.type !== "same" || d.line.trim())
                .map((d, i) => <DiffLine key={i} line={d.line} type={d.type} />)}
            </div>
          </div>
        )}

        {/* AI ANALYSIS */}
        {tab === "ai" && (
          <div className="ai-panel">

            {!aiReport && !loading && !error && (
              <div className="ai-empty">
                <div className="ai-empty-icon">✦</div>
                <div>
                  <div className="ai-empty-title">AI-Powered Document Analysis</div>
                  <div className="ai-empty-desc">
                    GPT-4o will compare both documents and return a structured report — new sections,
                    removed fields, compliance impact, and recommended actions.
                  </div>
                </div>
                <button onClick={runAIComparison} className="ai-run-btn">
                  ✦ Run AI Analysis
                </button>
              </div>
            )}

            {loading && (
              <div className="ai-loading">
                <div className="ai-spinner" />
                <div className="ai-loading-text">{progress}</div>
              </div>
            )}

            {error && !loading && (
              <div className="ai-error">
                <span style={{ fontSize: 20 }}>⚠</span>
                <div>
                  <div className="ai-error-title">Analysis Failed</div>
                  <div className="ai-error-msg">{error}</div>
                  <button onClick={runAIComparison} className="ai-retry-btn">Retry</button>
                </div>
              </div>
            )}

            {aiReport && !loading && (() => {
              const imp = IMPACT_STYLE[aiReport.impact] || IMPACT_STYLE.Medium;
              return (
                <div className="ai-report">

                  <div className="summary-card">
                    <div className="summary-body">
                      <div className="summary-label">SUMMARY</div>
                      <p className="summary-text">{aiReport.summary}</p>
                    </div>
                    <div className="impact-badge"
                      style={{ background: imp.bg, border: `1px solid ${imp.dot}44` }}>
                      <div className="impact-dot"
                        style={{ background: imp.dot, boxShadow: `0 0 8px ${imp.dot}` }} />
                      <div className="impact-label" style={{ color: imp.color }}>
                        {aiReport.impact} Impact
                      </div>
                    </div>
                  </div>

                  <div className="ai-3col">
                    <div className="ai-card">
                      <div className="sm-card-label" style={{ color: "#15803d" }}>
                        <span className="sm-badge-icon sm-badge-icon--added">+</span>
                        NEW SECTIONS ({aiReport.new_sections?.length || 0})
                      </div>
                      {aiReport.new_sections?.length > 0
                        ? aiReport.new_sections.map((s, i) => (
                            <div key={i} className="section-item section-item--added">{s}</div>
                          ))
                        : <div className="section-none">None</div>
                      }
                    </div>

                    <div className="ai-card">
                      <div className="sm-card-label" style={{ color: "#b91c1c" }}>
                        <span className="sm-badge-icon sm-badge-icon--removed">−</span>
                        REMOVED SECTIONS ({aiReport.removed_sections?.length || 0})
                      </div>
                      {aiReport.removed_sections?.length > 0
                        ? aiReport.removed_sections.map((s, i) => (
                            <div key={i} className="section-item section-item--removed">{s}</div>
                          ))
                        : <div className="section-none">None</div>
                      }
                    </div>

                    <div className="ai-card">
                      <div className="sm-card-label" style={{ color: "#6366f1" }}>
                        NEW FIELDS ({aiReport.new_fields?.length || 0})
                      </div>
                      <div className="new-fields-wrap">
                        {aiReport.new_fields?.length > 0
                          ? aiReport.new_fields.map((f, i) => (
                              <span key={i} className="field-chip">+ {f}</span>
                            ))
                          : <div className="section-none">None</div>
                        }
                      </div>
                    </div>
                  </div>

                  {aiReport.modified_fields?.length > 0 && (
                    <div className="ai-card">
                      <div className="modified-label">
                        MODIFIED FIELDS ({aiReport.modified_fields.length})
                      </div>
                      <div className="modified-list">
                        {aiReport.modified_fields.map((f, i) => (
                          <div key={i} className="modified-item">
                            <div className="modified-item-title">{f.field}</div>
                            <div className="modified-item-cols">
                              <div className="modified-before">
                                <div className="col-label col-label--before">BEFORE</div>
                                <div className="col-val--before">{f.old}</div>
                              </div>
                              <div className="modified-after">
                                <div className="col-label col-label--after">AFTER</div>
                                <div className="col-val--after">{f.new}</div>
                              </div>
                            </div>
                            {f.reason && <div className="modified-reason">{f.reason}</div>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="ai-2col">
                    <div className="ai-card">
                      <div className="compliance-label">COMPLIANCE NOTE</div>
                      <p className="card-text" style={{ color: "#1e293b" }}>{aiReport.compliance_notes}</p>
                    </div>
                    <div className="action-card">
                      <div className="action-label">RECOMMENDED ACTION</div>
                      <p className="card-text" style={{ color: "#15803d" }}>{aiReport.recommended_action}</p>
                    </div>
                  </div>

                  <div>
                    <button onClick={runAIComparison} className="rerun-btn">
                      ↺ Re-run Analysis
                    </button>
                  </div>
                </div>
              );
            })()}
          </div>
        )}
      </div>

      {/* ── FOOTER ── */}
      <footer className="footer">
        <span>Prototype — EXL Service × Novologix</span>
        <span>Powered by OpenAI GPT-4o</span>
      </footer>
    </div>
  );
}

# Architecture — doc-compare

## Overview

A single-page React application that lets users upload two documents, compare them side-by-side, view a line-level diff, and run an AI-powered analysis via OpenAI GPT-4o.

---

## Tech Stack

| Layer       | Technology                         |
|-------------|------------------------------------|
| UI          | React 19 (Create React App)        |
| Styling     | Plain CSS (`App.css`)              |
| Docx parsing| `mammoth` (browser-side)           |
| AI backend  | OpenAI GPT-4o (`/v1/chat/completions`) |
| Dev proxy   | `http-proxy-middleware` (`setProxy.jsx`) |

---

## File Structure

```
doc-compare/
├── public/
│   └── index.html              # HTML shell — mounts #root
├── src/
│   ├── index.js                # Entry point — ReactDOM.createRoot → <App />
│   ├── App.js                  # Entire application logic and JSX
│   ├── App.css                 # All component styles (separated from App.js)
│   ├── index.css               # Global resets / body defaults
│   └── setProxy.jsx            # Dev proxy: /api → https://api.anthropic.com
└── package.json
```

---

## Component Tree

```
<App>                           # Single stateful component (App.js)
├── <header>                    # Top nav: branding, stat chips, upload buttons, AI button
├── <div.tab-bar>               # Tab switcher: Side by Side | Line Diff | AI Analysis
└── <div.content>
    ├── [tab=compare]
    │   └── <div.compare-grid>  # CSS grid 1fr 1fr
    │       ├── <div.panel>     # Old document panel
    │       │   ├── DropZone    # label + hidden <input file> + drag-and-drop handlers
    │       │   └── <textarea>  # Shown once file is loaded; directly editable
    │       └── <div.panel>     # New document panel (same structure)
    ├── [tab=diff]
    │   └── <div.diff-view>
    │       ├── Legend bar
    │       └── <DiffLine> ×N   # One per line from computeDiff()
    └── [tab=ai]
        └── <div.ai-panel>
            ├── Empty state
            ├── Loading spinner
            ├── Error card
            └── AI Report cards (summary, sections, fields, compliance, action)
```

`DiffLine` is the only extracted sub-component. Everything else lives inline in `App`.

---

## State

All state lives in the `App` component via `useState`:

| State variable  | Type    | Purpose                                         |
|-----------------|---------|-------------------------------------------------|
| `tab`           | string  | Active tab: `"compare"` \| `"diff"` \| `"ai"`  |
| `oldDoc`        | string  | Text content of the old document                |
| `newDoc`        | string  | Text content of the new document                |
| `oldFileName`   | string  | Display name of the uploaded old file           |
| `newFileName`   | string  | Display name of the uploaded new file           |
| `aiReport`      | object  | Parsed JSON from GPT-4o (null until run)        |
| `loading`       | boolean | AI request in-flight                            |
| `error`         | string  | Last AI error message                           |
| `progress`      | string  | Step label shown during loading                 |

No external state library is used.

---

## Data Flow

### File Upload

```
User picks file (click or drag-and-drop)
  └─► processFile(side, file)
        ├── .docx → mammoth.extractRawText() → plain text
        └── .txt  → FileReader.readAsText()
              └─► setOldDoc / setNewDoc  (triggers re-render)
```

### Diff Computation

`computeDiff(oldDoc, newDoc)` runs on every render (no memoization). It implements the **LCS (Longest Common Subsequence)** algorithm:

1. Build an `(m+1) × (n+1)` DP table over the split lines.
2. Backtrack to produce an array of `{ line, type }` objects — `"added"`, `"removed"`, or `"same"`.
3. Returns `{ result, stats }` — stats drive the header chips.

### AI Analysis

```
runAIComparison()
  └─► POST https://api.openai.com/v1/chat/completions
        model: gpt-4o
        system: "respond with valid JSON only"
        user:   first 3000 chars of each doc + JSON schema
  └─► Parse response → setAiReport(parsed)
  └─► setTab("ai")   (auto-switch to AI tab)
```

The API key is read from `process.env.REACT_APP_OPENAI_KEY` (set in `.env`). It is sent directly from the browser — suitable for local/demo use only.

---

## Styling

All styles are in `src/App.css`, organized by section:

- Static layout and typography → CSS classes (`className`)
- Data-driven colors (stat chip colors, panel header accent, impact badge) → inline `style` props — these values come from runtime data so cannot be static classes

Key CSS patterns used:

| Pattern          | Used for                                      |
|------------------|-----------------------------------------------|
| `display: flex`  | Header, tab bar, cards, drop zone, footer     |
| `display: grid`  | Side-by-side panels, 3-col AI grid, field cols|
| `min-height: 0`  | Prevents flex children from overflowing       |
| BEM-style classes| `.tab-btn--active`, `.diff-line--added`, etc. |
| CSS animations   | `@keyframes spin`, `@keyframes pulse-dot`     |

---

## Dev Proxy (`setProxy.jsx`)

Proxies `/api/*` → `https://api.anthropic.com` during development (for Anthropic API calls). Not currently used — the app calls OpenAI directly. Available for future Claude integration.

---

## Environment Variables

| Variable                 | Required | Purpose              |
|--------------------------|----------|----------------------|
| `REACT_APP_OPENAI_KEY`   | Yes      | OpenAI API key       |

Create a `.env` file in the project root:

```
REACT_APP_OPENAI_KEY=sk-...
```

Restart the dev server after changes.

---

## Known Constraints

- `computeDiff` is O(m × n) in time and space — large documents (thousands of lines) will be slow.
- The OpenAI key is exposed in the browser bundle — not safe for production deployment.
- Only `.txt` and `.docx` are supported; `.pdf` requires a separate extraction library.
- The AI prompt truncates each document to 3,000 characters, so very long documents get partial analysis.

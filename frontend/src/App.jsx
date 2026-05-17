import React, { useState, useRef, useCallback, useEffect } from 'react';
import axios from 'axios';
import Editor from '@monaco-editor/react';
import './index.css';

const API = 'http://localhost:8000';

/* ------------------------------------------------------------------ */
/* Helpers                                                              */
/* ------------------------------------------------------------------ */
const scoreClass = (pct) => {
  if (pct >= 75) return 'excellent';
  if (pct >= 50) return 'good';
  return 'poor';
};

const ScoreBadge = ({ label, score }) => {
  if (score === null) return null;
  const pct = Math.round(score * 100);
  const cls = scoreClass(pct);
  return (
    <div className={`score-badge ${cls}`}>
      {label}: {pct}%
    </div>
  );
};

const ProgressBar = ({ score }) => {
  if (score === null) return null;
  const pct = Math.round(score * 100);
  const cls = scoreClass(pct);
  return (
    <div className="progress-bar-wrap">
      <div className={`progress-bar-fill ${cls}`} style={{ width: `${pct}%` }} />
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* File Drop Zone                                                       */
/* ------------------------------------------------------------------ */
const FileDrop = ({ file, onChange, label }) => (
  <div className="file-drop">
    <input type="file" accept=".pdf,.txt" onChange={(e) => onChange(e.target.files[0])} />
    {file
      ? <span className="file-name">📄 {file.name}</span>
      : <>
          <span style={{ fontSize: 18 }}>⬆</span>
          <span>{label}</span>
          <span style={{ fontSize: 10 }}>PDF or TXT</span>
        </>
    }
  </div>
);

/* ------------------------------------------------------------------ */
/* App                                                                  */
/* ------------------------------------------------------------------ */
export default function App() {
  // --- Input mode: 'text' | 'file' ---
  const [resumeMode, setResumeMode] = useState('text');
  const [jdMode, setJdMode] = useState('text');

  // --- Inputs ---
  const [resumeText, setResumeText] = useState('');
  const [jdText, setJdText] = useState('');
  const [resumeFile, setResumeFile] = useState(null);
  const [jdFile, setJdFile] = useState(null);

  // --- Results ---
  const [initialEval, setInitialEval] = useState(null);    // full /evaluate response
  const [improvedEval, setImprovedEval] = useState(null);
  const [latexCode, setLatexCode] = useState('% Generated LaTeX will appear here…');
  const [pdfUrl, setPdfUrl] = useState('');

  // --- UI state ---
  const [phase, setPhase] = useState('idle'); // idle | evaluating | generating | compiling | done
  const [isCompiling, setIsCompiling] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatting, setIsChatting] = useState(false);

  const compileTimer = useRef(null);
  const chatBottomRef = useRef(null);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  /* ---- Build FormData for /evaluate ---- */
  const buildEvalForm = useCallback((rText, rFile, jText, jFile) => {
    const fd = new FormData();
    if (rFile)  fd.append('resume', rFile);
    else        fd.append('resume_text_input', rText);
    if (jFile)  fd.append('job_description', jFile);
    else        fd.append('jd_text_input', jText);
    fd.append('use_rag', 'true');
    return fd;
  }, []);

  /* ---- Compile LaTeX → PDF ---- */
  const compileLatex = useCallback(async (code) => {
    if (!code || code.trim().length < 20) return;
    setIsCompiling(true);
    try {
      const resp = await axios.post(`${API}/compile-latex`, { latex_content: code }, { responseType: 'blob' });
      const blob = new Blob([resp.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
      setPdfUrl(url);
    } catch (err) {
      console.warn('Compile error (non-fatal):', err?.response?.data || err.message);
    } finally {
      setIsCompiling(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---- Editor change with 2-second debounce ---- */
  const handleEditorChange = (val) => {
    setLatexCode(val);
    if (compileTimer.current) clearTimeout(compileTimer.current);
    compileTimer.current = setTimeout(() => compileLatex(val), 2000);
  };

  /* ---- Main pipeline ---- */
  const handleRun = async () => {
    try {
      // Validate inputs
      const hasResume = resumeMode === 'file' ? !!resumeFile : !!resumeText.trim();
      const hasJD     = jdMode     === 'file' ? !!jdFile     : !!jdText.trim();
      if (!hasResume || !hasJD) {
        alert('Please provide both your resume and the job description.');
        return;
      }

      setInitialEval(null);
      setImprovedEval(null);
      setPdfUrl('');
      setLatexCode('% Generating…');

      // ---------- Step 1: Evaluate original resume ----------
      setPhase('evaluating');
      const evalForm = buildEvalForm(resumeText, resumeFile, jdText, jdFile);
      const evalResp = await axios.post(`${API}/evaluate`, evalForm);
      const evalData = evalResp.data;
      setInitialEval(evalData);

      const extractedResumeText = evalData.resume_text || resumeText;
      const extractedJdText     = evalData.jd_text     || jdText;

      // Build suggestions string from RAG LLM response + recommendations
      const ragText = evalData.rag_evaluation?.llm_response || '';
      const recs    = evalData.interpretation?.recommendations?.join('; ') || '';
      const suggestionContext = [ragText, recs].filter(Boolean).join('\n\n');

      // ---------- Step 2: Generate optimised LaTeX ----------
      setPhase('generating');
      const genResp = await axios.post(`${API}/generate-latex`, {
        resume_text: extractedResumeText,
        jd_text:     extractedJdText,
        evaluation_suggestions: suggestionContext || null,
      });
      const generatedLatex = genResp.data.latex;
      setLatexCode(generatedLatex);

      // ---------- Step 3: Compile to PDF ----------
      setPhase('compiling');
      await compileLatex(generatedLatex);

      // ---------- Step 4: Evaluate improved resume ----------
      const improvedForm = new FormData();
      improvedForm.append('resume_text_input', generatedLatex);  // use latex text as proxy
      improvedForm.append('jd_text_input', extractedJdText);
      improvedForm.append('use_rag', 'false');  // skip RAG for speed
      const improvedResp = await axios.post(`${API}/evaluate`, improvedForm);
      setImprovedEval(improvedResp.data);

      setPhase('done');
    } catch (err) {
      console.error(err);
      alert('Error: ' + (err?.response?.data?.error || err.message));
      setPhase('idle');
    }
  };

  /* ---- Chat ---- */
  const handleSend = async () => {
    if (!chatInput.trim() || isChatting) return;
    const userMsg = { role: 'user', content: chatInput.trim() };
    const next = [...chatMessages, userMsg];
    setChatMessages(next);
    setChatInput('');
    setIsChatting(true);
    try {
      const resp = await axios.post(`${API}/chat`, {
        messages: next,
        current_latex: latexCode,
      });
      const text = resp.data.response;
      setChatMessages([...next, { role: 'assistant', content: text }]);

      // Extract and apply updated LaTeX if present
      if (text.includes('```latex')) {
        const extracted = text.split('```latex')[1].split('```')[0].trim();
        setLatexCode(extracted);
        compileLatex(extracted);
      }
    } catch (err) {
      setChatMessages([...next, { role: 'assistant', content: '⚠ Error contacting agent.' }]);
    } finally {
      setIsChatting(false);
    }
  };

  /* ---- Phase label ---- */
  const phaseLabel = {
    idle:       null,
    evaluating: 'Evaluating resume…',
    generating: 'Generating optimised resume…',
    compiling:  'Compiling PDF…',
    done:       null,
  }[phase];

  const isRunning = phase !== 'idle' && phase !== 'done';

  /* ---------------------------------------------------------------- */
  /* Render                                                            */
  /* ---------------------------------------------------------------- */
  return (
    <div className="app-shell">

      {/* ===== TOPBAR ===== */}
      <div className="topbar">
        <div className="topbar-brand">CV<span>Scope</span></div>

        {/* Score badges */}
        <div style={{ display: 'flex', gap: 8, flex: 1, justifyContent: 'center', flexWrap: 'wrap' }}>
          {initialEval && (
            <ScoreBadge label="Initial Score" score={initialEval.score} />
          )}
          {improvedEval && (
            <ScoreBadge label="Improved Score" score={improvedEval.score} />
          )}
          {phaseLabel && (
            <span style={{ color: 'var(--txt-muted)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="spinner" /> {phaseLabel}
            </span>
          )}
        </div>

        <div className="topbar-actions">
          <button
            className="btn btn-sm"
            onClick={() => navigator.clipboard.writeText(latexCode)}
            title="Copy LaTeX"
          >
            Copy LaTeX
          </button>
          <a
            href={pdfUrl || '#'}
            download="resume.pdf"
            style={{ textDecoration: 'none' }}
            onClick={(e) => !pdfUrl && e.preventDefault()}
          >
            <button className="btn btn-sm btn-primary" disabled={!pdfUrl}>
              ↓ PDF
            </button>
          </a>
        </div>
      </div>

      {/* ===== WORKSPACE ===== */}
      <div className="workspace">

        {/* ===== SIDEBAR ===== */}
        <div className="sidebar">

          {/* Resume input */}
          <div className="sidebar-section">
            <div className="sidebar-section-title">Resume</div>
            <div className="mode-toggle">
              <button className={resumeMode === 'text' ? 'active' : ''} onClick={() => setResumeMode('text')}>Text</button>
              <button className={resumeMode === 'file' ? 'active' : ''} onClick={() => setResumeMode('file')}>File</button>
            </div>
            {resumeMode === 'text'
              ? <textarea
                  className="field-textarea"
                  rows={7}
                  value={resumeText}
                  onChange={(e) => setResumeText(e.target.value)}
                  placeholder="Paste your current resume…"
                />
              : <FileDrop file={resumeFile} onChange={setResumeFile} label="Click or drag resume PDF" />
            }
          </div>

          {/* JD input */}
          <div className="sidebar-section">
            <div className="sidebar-section-title">Job Description</div>
            <div className="mode-toggle">
              <button className={jdMode === 'text' ? 'active' : ''} onClick={() => setJdMode('text')}>Text</button>
              <button className={jdMode === 'file' ? 'active' : ''} onClick={() => setJdMode('file')}>File</button>
            </div>
            {jdMode === 'text'
              ? <textarea
                  className="field-textarea"
                  rows={7}
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  placeholder="Paste the job description…"
                />
              : <FileDrop file={jdFile} onChange={setJdFile} label="Click or drag JD PDF" />
            }
          </div>

          {/* Run button */}
          <div className="sidebar-section">
            <button
              className="btn btn-primary btn-full"
              onClick={handleRun}
              disabled={isRunning}
            >
              {isRunning
                ? <><span className="spinner" /> Running…</>
                : '⚡ Evaluate & Generate'}
            </button>
          </div>

          {/* Initial score details */}
          {initialEval && (
            <div className="sidebar-section">
              <div className="sidebar-section-title">
                Initial Analysis
                <span className={`tag ${scoreClass(Math.round(initialEval.score*100))}`} style={{ marginLeft: 8 }}>
                  {initialEval.match_level}
                </span>
              </div>
              <ProgressBar score={initialEval.score} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--txt-muted)', marginTop: 4 }}>
                <span>Score</span>
                <strong style={{ color: 'var(--txt)' }}>{Math.round(initialEval.score * 100)}%</strong>
              </div>
              {initialEval.interpretation?.recommendations && (
                <ul className="rec-list">
                  {initialEval.interpretation.recommendations.slice(0, 3).map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}
            </div>
          )}

          {/* Improved score details */}
          {improvedEval && (
            <div className="sidebar-section">
              <div className="sidebar-section-title">
                Improved Score
                <span className={`tag ${scoreClass(Math.round(improvedEval.score*100))}`} style={{ marginLeft: 8 }}>
                  {improvedEval.match_level}
                </span>
              </div>
              <ProgressBar score={improvedEval.score} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--txt-muted)', marginTop: 4 }}>
                <span>Score</span>
                <strong style={{ color: 'var(--green)' }}>{Math.round(improvedEval.score * 100)}%</strong>
              </div>
              {initialEval && (
                <div style={{ fontSize: 11, color: 'var(--green)', marginTop: 4 }}>
                  ▲ +{Math.max(0, Math.round((improvedEval.score - initialEval.score) * 100))}% improvement
                </div>
              )}
            </div>
          )}

          {/* LLM suggestions */}
          {initialEval?.rag_evaluation?.enabled && initialEval.rag_evaluation.llm_response && (
            <div className="sidebar-section" style={{ flex: 1 }}>
              <div className="sidebar-section-title">AI Suggestions</div>
              <div className="suggestions-box">
                {initialEval.rag_evaluation.llm_response}
              </div>
            </div>
          )}

          {/* Agent chat */}
          <div className="sidebar-section" style={{ flex: 1, minHeight: 220, paddingBottom: 0 }}>
            <div className="sidebar-section-title">Agent Chat</div>
            <div className="chat-wrap">
              <div className="chat-messages">
                {chatMessages.length === 0 && (
                  <div style={{ color: 'var(--txt-muted)', fontSize: 11, textAlign: 'center', marginTop: 12 }}>
                    Ask me to tweak the generated resume!
                  </div>
                )}
                {chatMessages.map((m, i) => {
                  const display = m.content.includes('```latex')
                    ? '✅ Resume updated in editor.'
                    : m.content;
                  return <div key={i} className={`chat-msg ${m.role}`}>{display}</div>;
                })}
                {isChatting && <div className="chat-msg thinking">Thinking…</div>}
                <div ref={chatBottomRef} />
              </div>
              <div className="chat-input-row">
                <input
                  className="chat-input"
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder="e.g. Make my title more senior…"
                  disabled={isChatting}
                />
                <button className="btn btn-sm btn-primary" onClick={handleSend} disabled={isChatting}>
                  ↑
                </button>
              </div>
            </div>
          </div>

        </div>
        {/* end sidebar */}

        {/* ===== EDITOR PANE ===== */}
        <div className="editor-pane">
          <div className="pane-header">
            LaTeX Editor
            {isCompiling && <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--yellow)', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>
              <span className="status-dot compiling" /> Compiling…
            </span>}
          </div>
          <div className="pane-body">
            <Editor
              height="100%"
              defaultLanguage="latex"
              theme="vs-dark"
              value={latexCode}
              onChange={handleEditorChange}
              options={{
                minimap: { enabled: false },
                wordWrap: 'on',
                fontSize: 13,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                renderLineHighlight: 'line',
                padding: { top: 8 },
              }}
            />
          </div>
        </div>

        {/* ===== PREVIEW PANE ===== */}
        <div className="preview-pane">
          <div className="pane-header" style={{ background: '#f0f0f0', color: '#555', borderBottom: '1px solid #ddd' }}>
            PDF Preview
          </div>
          <div className="pane-body">
            {pdfUrl
              ? <iframe src={pdfUrl} width="100%" height="100%" style={{ border: 'none', display: 'block' }} title="PDF Preview" />
              : <div className="preview-placeholder">
                  <span style={{ fontSize: 36 }}>📄</span>
                  <span>Compiled PDF will appear here</span>
                  <span style={{ fontSize: 11, color: '#aaa' }}>Click "Evaluate & Generate" to start</span>
                </div>
            }
          </div>
        </div>

      </div>
      {/* end workspace */}

    </div>
  );
}

import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Editor from '@monaco-editor/react';
import './index.css';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [resumeText, setResumeText] = useState('');
  const [jdText, setJdText] = useState('');
  const [latexCode, setLatexCode] = useState('% Your LaTeX code will appear here...');
  const [pdfUrl, setPdfUrl] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCompiling, setIsCompiling] = useState(false);
  
  // Chat state
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatting, setIsChatting] = useState(false);

  // Debounce for editor
  const compileTimeout = useRef(null);

  const handleGenerate = async () => {
    if (!resumeText || !jdText) {
      alert("Please enter both Resume and Job Description text.");
      return;
    }
    
    setIsGenerating(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/generate-latex`, {
        resume_text: resumeText,
        jd_text: jdText
      });
      setLatexCode(response.data.latex);
      compileLatex(response.data.latex);
    } catch (error) {
      console.error("Error generating LaTeX:", error);
      alert("Failed to generate LaTeX");
    } finally {
      setIsGenerating(false);
    }
  };

  const compileLatex = async (code) => {
    setIsCompiling(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/compile-latex`, {
        latex_content: code
      }, { responseType: 'blob' });
      
      const file = new Blob([response.data], { type: 'application/pdf' });
      const fileURL = URL.createObjectURL(file);
      setPdfUrl(fileURL);
    } catch (error) {
      console.error("Error compiling LaTeX:", error);
      // We don't alert here to avoid annoying popups while typing, just log it.
    } finally {
      setIsCompiling(false);
    }
  };

  const handleEditorChange = (value) => {
    setLatexCode(value);
    
    if (compileTimeout.current) {
      clearTimeout(compileTimeout.current);
    }
    
    // Debounce compile by 2 seconds
    compileTimeout.current = setTimeout(() => {
      compileLatex(value);
    }, 2000);
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim()) return;
    
    const newUserMsg = { role: 'user', content: chatInput };
    const updatedMessages = [...messages, newUserMsg];
    setMessages(updatedMessages);
    setChatInput('');
    setIsChatting(true);
    
    try {
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        messages: updatedMessages,
        current_latex: latexCode
      });
      
      const botResponseText = response.data.response;
      setMessages([...updatedMessages, { role: 'assistant', content: botResponseText }]);
      
      // If the bot returned a LaTeX block, extract and update it
      if (botResponseText.includes("```latex")) {
        const extractedLatex = botResponseText.split("```latex")[1].split("```")[0].trim();
        setLatexCode(extractedLatex);
        compileLatex(extractedLatex);
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages([...updatedMessages, { role: 'assistant', content: 'Sorry, I encountered an error.' }]);
    } finally {
      setIsChatting(false);
    }
  };

  return (
    <div className="layout-container">
      <div className="header">
        <h1>AI Resume Evaluator & Editor</h1>
        <div>
          <button style={{ marginRight: '10px' }} onClick={() => navigator.clipboard.writeText(latexCode)}>
            Copy LaTeX
          </button>
          <a href={pdfUrl} download="resume.pdf" style={{ textDecoration: 'none' }}>
            <button className="primary" disabled={!pdfUrl}>
              Download PDF
            </button>
          </a>
        </div>
      </div>

      <div className="main-content">
        <div className="sidebar">
          <div className="input-section glass-panel">
            <div className="input-group">
              <label>Resume Text</label>
              <textarea 
                value={resumeText} 
                onChange={(e) => setResumeText(e.target.value)} 
                placeholder="Paste your current resume here..."
              />
            </div>
            <div className="input-group">
              <label>Job Description</label>
              <textarea 
                value={jdText} 
                onChange={(e) => setJdText(e.target.value)} 
                placeholder="Paste the job description here..."
              />
            </div>
            <button className="primary" onClick={handleGenerate} disabled={isGenerating}>
              {isGenerating ? 'Generating...' : 'Generate Resume'}
            </button>
          </div>

          <div className="chat-container">
            <div className="section-header">Agent Chat</div>
            <div className="chat-messages">
              {messages.length === 0 && (
                <div style={{ color: 'var(--text-secondary)', textAlign: 'center', marginTop: '20px' }}>
                  Ask me to tweak the generated resume!
                </div>
              )}
              {messages.map((msg, idx) => (
                <div key={idx} className={`chat-message ${msg.role}`}>
                  {msg.content.includes("```latex") 
                    ? "I have updated the LaTeX code. (Code block hidden for brevity)"
                    : msg.content}
                </div>
              ))}
              {isChatting && <div className="chat-message assistant">Thinking...</div>}
            </div>
            <div className="chat-input-area">
              <input 
                type="text" 
                value={chatInput} 
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="E.g., Make my job title sound more senior..."
              />
              <button className="primary" onClick={handleSendMessage} disabled={isChatting}>
                Send
              </button>
            </div>
          </div>
        </div>

        <div className="editor-preview-container">
          <div className="editor-section">
            <div className="section-header">
              LaTeX Code
              {isCompiling && <span style={{ fontSize: '0.8rem', color: 'var(--accent-color)' }}>Compiling...</span>}
            </div>
            <div className="editor-body">
              <Editor
                height="100%"
                defaultLanguage="latex"
                theme="vs-dark"
                value={latexCode}
                onChange={handleEditorChange}
                options={{
                  minimap: { enabled: false },
                  wordWrap: 'on',
                  fontSize: 14,
                }}
              />
            </div>
          </div>

          <div className="preview-section">
            <div className="section-header">PDF Preview</div>
            <div className="preview-body">
              {pdfUrl ? (
                <iframe src={pdfUrl} width="100%" height="100%" style={{ border: 'none' }} title="PDF Preview" />
              ) : (
                <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: '#666' }}>
                  PDF will appear here after generation.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;

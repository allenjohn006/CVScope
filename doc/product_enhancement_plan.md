# Enhance AI Resume Evaluation System to an Industry-Level Product

This plan details the steps to transform the existing Streamlit-based AI Resume Evaluation System into a robust, agentic web application. The upgraded system will allow users to submit their resumes and job descriptions (as text or PDF), receive chunked analysis and scoring, interact with an AI agent to suggest changes, and dynamically generate a new resume in LaTeX.

The interface will feature a side-by-side view where the user can actively edit the generated LaTeX code. Changes to the code will automatically trigger a recompilation to update the displayed PDF.

## User Review Required

> [!WARNING]
> **Bidirectional Editing Constraint**: While it's completely feasible to provide a live code editor where editing the LaTeX code automatically recompiles and updates the PDF, it is extremely difficult to allow users to directly click and edit text *inside* the compiled PDF to update the underlying LaTeX. 
> **Proposed Solution**: 
> 1. Users can manually edit the LaTeX code directly in the code editor (which auto-updates the PDF).
> 2. For text-based edits, users can simply type their requested changes into the **Agent Chat** (e.g., "Change the text in my latest experience from X to Y"). The AI agent will automatically locate the section, update the LaTeX code, and trigger a recompile. Does this workflow meet your needs for the "vice versa" editing?

> [!IMPORTANT]
> **LaTeX Compilation Environment**: To compile LaTeX into a PDF locally on the server (backend), we will need a LaTeX distribution installed on your machine (e.g., TeX Live or MiKTeX on Windows) so that the `pdflatex` command is available. Alternatively, we could use an external API for compilation. Let me know if you have a local compiler.

> [!IMPORTANT]
> **Frontend Framework Selection**: We will use **Vite + React** for the frontend. This is necessary to support complex features like the Monaco code editor (for live LaTeX editing) and smooth state management for auto-recompilation.

## Proposed Changes

### Backend Updates

#### [MODIFY] api.py
- **Add Text Input Support**: Update endpoints to accept raw text alongside PDF uploads.
- **Add Agent Endpoints**: Create an interactive `/chat` endpoint to allow iterative suggestions for the resume. The agent can modify the LaTeX state based on text requests.
- **Add LaTeX Generation Endpoint**: Create an endpoint that takes the modified resume content, passes it to the LLM to write a clean LaTeX resume, and returns the LaTeX string.
- **Add LaTeX Compilation Endpoint**: Create an endpoint to compile the generated LaTeX code into a PDF (using `pdflatex`) and return the PDF file for the frontend to render.

#### [NEW] latex_engine.py
- A dedicated module to handle running subprocess calls to `pdflatex`, managing temporary `.tex` files, and retrieving the compiled `.pdf` files securely.

#### [MODIFY] llm.py
- Add specialized prompt templates for suggesting resume changes, generating strict LaTeX code, and updating existing LaTeX code based on user conversational input.

### Frontend Updates

#### [DELETE] frontend/app.py
- Remove the existing Streamlit application.

#### [NEW] New Frontend Architecture (Vite + React)
- **Scaffolding**: Initialize a new Vite React app in the `frontend` directory.
- **Components**:
  - **Input Section**: Rich text areas for Resume and JD input.
  - **Agent Chat Interface**: A chat window to discuss improvements and request text changes to the resume.
  - **Live Code Editor**: Implement `Monaco Editor` for the LaTeX source code. It will include a debounce function so that pausing typing automatically triggers a recompile API call.
  - **Live PDF Viewer**: An `iframe` or `react-pdf` component to display the compiled result side-by-side with the code.
  - **Export Options**: Buttons to "Download PDF" and "Copy LaTeX".

## Verification Plan

### Automated Tests
- Test the new `/agent` endpoint to ensure it maintains conversation context and correctly updates LaTeX state.
- Verify `latex_engine.py` can compile a basic dummy `.tex` file into a `.pdf` without hanging.

### Manual Verification
- Start the FastAPI backend and Vite frontend.
- Upload a sample PDF resume and JD.
- Open the code editor and modify a line of LaTeX; verify the PDF automatically updates after a brief delay.
- Use the agent chat to request a specific text change (e.g., "Fix the typo in my job title"); verify the agent updates the LaTeX code and the PDF reflects the fix.

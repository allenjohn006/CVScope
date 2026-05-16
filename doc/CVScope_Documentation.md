# CVScope - AI Resume Evaluation System Documentation

## 1. Overview
CVScope is an AI-powered system designed to evaluate the compatibility between a candidate's resume and a specific job description. By employing state-of-the-art Natural Language Processing (NLP) techniques, neural embeddings, and Retrieval-Augmented Generation (RAG), the system computes semantic similarity and provides actionable, context-aware insights for applicants.

## 2. System Architecture

The project represents a decoupled, modern architecture:
- **Frontend (Streamlit):** An interactive, user-friendly UI for file uploads and visual feedback visualization.
- **Backend (FastAPI):** A high-performance RESTful API that handles document processing, orchestration, mathematical similarity calculation, and the RAG pipeline execution.
- **AI/LLM Layer:** Leverages external models (via OpenRouter APIs) for vector embeddings and conversational inferences (Generative AI generation).

## 3. How It Works

### Step-by-Step Workflow
1. **Document Upload:** The user uploads two PDF documents (Resume and Job Description) via the Streamlit frontend.
2. **Document Processing:** 
   - The FastAPI backend receives the files and persists them temporarily.
   - Text is parsed and extracted using `pdfplumber` (supported by Tesseract OCR as a fallback for scanned pages).
3. **Chunking & Embedding:**
   - The raw texts are divided into manageable chunks using configurable chunking strategies (e.g., word-based splitting) to ensure texts fit into the context window of AI models.
   - Embeddings (mathematical vector arrays representing semantic meaning, commonly with 384 dimensions) are generated for both the Resume and the Job Description texts.
4. **Baseline Similarity Computing:**
   - A mathematical similarity comparison is performed between the resume embeddings and the job description embeddings.
5. **RAG Pipeline (Optional but Recommended):**
   - The chunked vectors are stored in two respective **FAISS** vector databases.
   - The pipeline retrieves the most relevant chunks from the resume (querying *"candidate experience and skills"*) and the JD (querying *"job requirements and skills"*).
   - This context is constructed into a prompt and sent to an LLM to generate qualitative reasoning and improvement points.
6. **Result Generation:** The pipeline converges both the quantitative percentage scores and the qualitative LLM feedback, which Streaming UI displays beautifully.

## 4. Evaluation & Accuracy

### Similarity Calculation (Quantitative Engine)
The core capability revolves around the `SimilarityCalculator`. The accuracy and baseline scores are derived through linear algebraic comparisons of the document vectors.

- **Primary Metric:** **Cosine Similarity** is the default algorithm applied. It calculates the normalized dot product of the two matrices: 
  $$ \text{Cosine Similarity} = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\|\|\mathbf{B}\|} $$
- **Alternatives:** Euclidean Distance and pure Dot Product capabilities are also built-in for alternate assessment modes. 

### Grading Thresholds
The raw Cosine similarity metric (bounded between 0.0 and 1.0 threshold) is converted to a percentage and graded using the following thresholds:
- **Score $\ge$ 75%** ($\ge$ 0.75): **Excellent Match** 
- **Score $\ge$ 50%** ($\ge$ 0.50): **Good Match** 
- **Score $<$ 50%** ($<$ 0.50): **Needs Improvement**

### Contextual Evaluation Accuracy (RAG)
Because pure Cosine similarity lacks nuance (e.g., matching years of experience explicitly), the RAG pipeline is used to elevate overall perceived accuracy:
- Relevant subsets of documents are fed to a robust generative LLM explicitly with instructions to verify semantic logic.
- Thus, the system doesn't just guess accuracy mathematically; it validates *why* a candidate fits the role.

## 5. Technology Stack in Detail

* **FastAPI:** Core backend controller handling asynchronous HTTP requests.
* **Streamlit:** Frontend visualization tool, making charting metrics and UI components fast.
* **FAISS (Facebook AI Similarity Search):** Empowers the RAG pipeline by handling high-speed retrieval mechanism.
* **Numpy:** Empowers manual numeric operations required for mathematical similarity scores.
* **LLM Integrations (OpenRouter):** Abstracted neural layers to leverage modern intelligence. 

## 6. Project Structure Overview
```text
CVScope/
├── backend/ 
│   ├── api.py (FastAPI App Definition)
│   ├── main.py (Orchestration logic)
│   ├── similarity.py (Numpy similarity algorithms)
│   ├── embeddings.py (Vectorization wrapper)
│   └── rag/ (Contains FAISS logic, prompt logic, and retrievers)
├── frontend/
│   └── app.py (Streamlit UI layout)
└── doc/
    └── CVScope_Documentation.md
```
"""
FastAPI backend for the AI Resume Evaluation System
"""
import os
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from dotenv import load_dotenv
from typing import Optional, List
from pydantic import BaseModel

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

print("Starting imports...")

try:
    from pdf_loader import PDFLoader
    print("✓ PDFLoader imported")
    from chunker import TextChunker
    print("✓ TextChunker imported")
    from embeddings import EmbeddingGenerator
    print("✓ EmbeddingGenerator imported")
    from llm import call_llm, call_llm_chat, LATEX_GENERATION_SYSTEM_PROMPT, AGENT_SYSTEM_PROMPT
    print("✓ call_llm imported")
    from rag.vector_store import VectorStore
    print("✓ VectorStore imported")
    from rag.rag_pipeline import RAGPipeline
    print("✓ RAGPipeline imported")
    from main import analyze
    print("✓ analyze imported")
    from latex_engine import latex_engine
    print("✓ latex_engine imported")
except Exception as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()

app = FastAPI(title="AI Resume Evaluation System API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = Path("temp_uploads")
TEMP_DIR.mkdir(exist_ok=True)

# Initialize components
pdf_loader = PDFLoader()
chunker = TextChunker()
embedding_gen = EmbeddingGenerator()


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    current_latex: Optional[str] = None

class GenerateLatexRequest(BaseModel):
    resume_text: str
    jd_text: str
    evaluation_suggestions: Optional[str] = None  # missing keywords / suggestions from /evaluate

class CompileLatexRequest(BaseModel):
    latex_content: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_text(upload: Optional[UploadFile], text_input: Optional[str], label: str, saved_path: Path) -> str:
    """Synchronous extraction — caller must have already written bytes to saved_path if upload exists."""
    if saved_path and saved_path.exists():
        return pdf_loader.load_pdf(str(saved_path))
    elif text_input:
        return text_input
    else:
        raise ValueError(f"No {label} provided (neither file nor text)")


async def save_upload(upload: UploadFile, dest: Path):
    content = await upload.read()
    with open(dest, "wb") as f:
        f.write(content)


def get_interpretation(score: float) -> dict:
    if score >= 0.75:
        return {
            "level": "Excellent Match",
            "message": "Your resume is an excellent match for this job!",
            "recommendations": [
                "Your skills align well with the job requirements",
                "Proceed with confidence in your application",
                "Highlight your strongest matches in the cover letter",
            ],
        }
    elif score >= 0.50:
        return {
            "level": "Good Match",
            "message": "Your resume is a good match for this job.",
            "recommendations": [
                "Highlight relevant skills and experience",
                "Add more keywords from the job description",
                "Emphasize matching accomplishments",
                "Use the cover letter to explain your fit",
            ],
        }
    else:
        return {
            "level": "Needs Improvement",
            "message": "Your resume may need some adjustments.",
            "recommendations": [
                "Identify key skills from the job description",
                "Add or emphasise relevant experience",
                "Consider gaining required certifications",
                "Reorder resume to highlight relevant skills",
                "Ensure you have domain experience",
            ],
        }


async def run_evaluation(resume_text: str, jd_text: str, chunk_size: int = 500, use_rag: bool = True) -> dict:
    """
    Core evaluation logic reused by both /evaluate and /evaluate-text.
    Accepts plain text for both resume and JD.
    """
    # Write temp files so analyze() has paths
    resume_path = TEMP_DIR / "eval_resume.txt"
    jd_path = TEMP_DIR / "eval_jd.txt"
    with open(resume_path, "w", encoding="utf-8") as f:
        f.write(resume_text)
    with open(jd_path, "w", encoding="utf-8") as f:
        f.write(jd_text)

    # Chunk
    text_chunker = TextChunker(chunk_size=chunk_size)
    resume_chunks = text_chunker.chunk_text(resume_text)
    jd_chunks = text_chunker.chunk_text(jd_text)

    if not resume_chunks or not jd_chunks:
        raise ValueError("Could not create chunks from the provided text")

    # Embeddings
    resume_embeddings = embedding_gen.generate_embeddings_batch(resume_chunks)
    jd_embeddings = embedding_gen.generate_embeddings_batch(jd_chunks)

    # Similarity
    similarity_score = analyze(str(resume_path), str(jd_path), chunk_size=chunk_size)

    # Match level
    if similarity_score >= 0.75:
        match_level = "Excellent"
    elif similarity_score >= 0.50:
        match_level = "Good"
    else:
        match_level = "Needs Improvement"

    result = {
        "success": True,
        "score": float(similarity_score),
        "score_percentage": f"{similarity_score * 100:.1f}%",
        "match_level": match_level,
        "analysis": {
            "raw_score": float(similarity_score),
            "percentage": round(similarity_score * 100, 1),
            "chunk_size": chunk_size,
            "resume_chunks_count": len(resume_chunks),
            "jd_chunks_count": len(jd_chunks),
        },
        "interpretation": get_interpretation(similarity_score),
    }

    # RAG evaluation
    if use_rag:
        try:
            print("Running RAG...")
            embedding_dim = len(resume_embeddings[0]) if resume_embeddings else 384
            resume_store = VectorStore(dim=embedding_dim, use_faiss=True)
            jd_store = VectorStore(dim=embedding_dim, use_faiss=True)
            resume_store.add(resume_embeddings, resume_chunks)
            jd_store.add(jd_embeddings, jd_chunks)
            rag_pipeline = RAGPipeline(resume_store, jd_store, top_k=5)
            rag_result = rag_pipeline.run()
            llm_response = call_llm(rag_result["prompt"])
            result["rag_evaluation"] = {
                "enabled": True,
                "llm_response": llm_response,
                "retrieved_resume_chunks": rag_result["resume_chunks"],
                "retrieved_jd_chunks": rag_result["jd_chunks"],
                "resume_relevance_scores": [float(s) for s in rag_result["resume_scores"]],
                "jd_relevance_scores": [float(s) for s in rag_result["jd_scores"]],
            }
        except Exception as e:
            print(f"RAG error (non-fatal): {e}")
            result["rag_evaluation"] = {"enabled": False, "error": str(e)}
    else:
        result["rag_evaluation"] = {"enabled": False}

    # Cleanup temp files
    try:
        resume_path.unlink(missing_ok=True)
        jd_path.unlink(missing_ok=True)
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "CVScope API running", "version": "2.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/evaluate")
async def evaluate_resume(
    resume: Optional[UploadFile] = File(None),
    resume_text_input: Optional[str] = Form(None),
    job_description: Optional[UploadFile] = File(None),
    jd_text_input: Optional[str] = Form(None),
    chunk_size: int = Form(default=500),
    use_rag: bool = Form(default=True),
):
    """Evaluate resume match — accepts PDF uploads or raw text."""
    resume_path = None
    jd_path = None
    try:
        print("=" * 60)
        print("POST /evaluate called")

        # --- Extract resume text ---
        resume_text = ""
        if resume and resume.filename:
            print(f"Resume File: {resume.filename}")
            resume_path = TEMP_DIR / f"resume_{resume.filename}"
            await save_upload(resume, resume_path)
            resume_text = pdf_loader.load_pdf(str(resume_path))
        elif resume_text_input:
            print("Resume Text Input Provided")
            resume_text = resume_text_input
        else:
            raise ValueError("No resume provided (neither file nor text)")

        # --- Extract JD text ---
        jd_text = ""
        if job_description and job_description.filename:
            print(f"JD File: {job_description.filename}")
            jd_path = TEMP_DIR / f"jd_{job_description.filename}"
            await save_upload(job_description, jd_path)
            jd_text = pdf_loader.load_pdf(str(jd_path))
        elif jd_text_input:
            print("JD Text Input Provided")
            jd_text = jd_text_input
        else:
            raise ValueError("No job description provided (neither file nor text)")

        print(f"✓ Resume: {len(resume_text)} chars | JD: {len(jd_text)} chars")

        result = await run_evaluation(resume_text, jd_text, chunk_size, use_rag)
        # Also return the extracted texts so the frontend can reuse them
        result["resume_text"] = resume_text
        result["jd_text"] = jd_text
        print("=" * 60)
        return JSONResponse(result)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
        return JSONResponse({"error": str(e), "success": False}, status_code=500)
    finally:
        if resume_path and Path(resume_path).exists():
            Path(resume_path).unlink(missing_ok=True)
        if jd_path and Path(jd_path).exists():
            Path(jd_path).unlink(missing_ok=True)


@app.post("/chat")
async def chat_agent(request: ChatRequest):
    try:
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
        if request.current_latex:
            messages.append({
                "role": "system",
                "content": f"The user's current resume LaTeX code is:\n```latex\n{request.current_latex}\n```",
            })
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        response_text = call_llm_chat(messages, model="openai/gpt-4o-mini")
        return {"response": response_text}
    except Exception as e:
        print(f"Chat error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/generate-latex")
async def generate_latex(request: GenerateLatexRequest):
    try:
        suggestions_block = ""
        if request.evaluation_suggestions:
            suggestions_block = f"\n\nEVALUATION SUGGESTIONS (missing keywords / skills to inject):\n{request.evaluation_suggestions}"

        prompt = (
            f"Resume Text:\n{request.resume_text}\n\n"
            f"Job Description:\n{request.jd_text}"
            f"{suggestions_block}\n\n"
            "Generate the optimised LaTeX resume now."
        )
        messages = [
            {"role": "system", "content": LATEX_GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        response_text = call_llm_chat(messages, model="openai/gpt-4o")

        # Strip any accidental markdown fences
        latex = response_text.strip()
        if "```latex" in latex:
            latex = latex.split("```latex")[1].split("```")[0].strip()
        elif "```" in latex:
            latex = latex.split("```")[1].split("```")[0].strip()

        return {"latex": latex}
    except Exception as e:
        print(f"Generate latex error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/compile-latex")
async def compile_latex(request: CompileLatexRequest, background_tasks: BackgroundTasks):
    try:
        pdf_path = latex_engine.compile_latex(request.latex_content)
        background_tasks.add_task(latex_engine.cleanup, pdf_path)
        return FileResponse(pdf_path, media_type="application/pdf", filename="resume.pdf")
    except Exception as e:
        print(f"Compile latex error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    print("Starting server...")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
"""
FastAPI backend for the AI Resume Evaluation System
"""
import os
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

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

app = FastAPI(
    title="AI Resume Evaluation System API",
    version="1.0.0"
)

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


@app.get("/")
async def root():
    return {"message": "API running", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


from typing import Optional, List
from fastapi.responses import FileResponse
from pydantic import BaseModel

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    current_latex: Optional[str] = None

class GenerateLatexRequest(BaseModel):
    resume_text: str
    jd_text: str

class CompileLatexRequest(BaseModel):
    latex_content: str

@app.post("/evaluate")
async def evaluate_resume(
    resume: Optional[UploadFile] = File(None),
    resume_text_input: Optional[str] = Form(None),
    job_description: Optional[UploadFile] = File(None),
    jd_text_input: Optional[str] = Form(None),
    chunk_size: int = Form(default=500),
    use_rag: bool = Form(default=True)
):
    """Evaluate resume match with real analysis"""
    resume_path = None
    jd_path = None
    
    try:
        print("=" * 60)
        print("POST /evaluate called")
        
        # Step 1: Extract text
        print("Step 1: Extracting text...")
        
        resume_text = ""
        if resume:
            print(f"Resume File: {resume.filename}")
            resume_path = TEMP_DIR / f"resume_{resume.filename}"
            with open(resume_path, "wb") as f:
                content = await resume.read()
                f.write(content)
            resume_text = pdf_loader.load_pdf(str(resume_path))
        elif resume_text_input:
            print("Resume Text Input Provided")
            resume_text = resume_text_input
        else:
            raise ValueError("No resume provided (neither file nor text)")
            
        jd_text = ""
        if job_description:
            print(f"JD File: {job_description.filename}")
            jd_path = TEMP_DIR / f"jd_{job_description.filename}"
            with open(jd_path, "wb") as f:
                content = await job_description.read()
                f.write(content)
            jd_text = pdf_loader.load_pdf(str(jd_path))
        elif jd_text_input:
            print("JD Text Input Provided")
            jd_text = jd_text_input
        else:
            raise ValueError("No job description provided (neither file nor text)")

        print(f"✓ Resume: {len(resume_text)} chars")
        print(f"✓ JD: {len(jd_text)} chars")
        
        # Step 2: Chunk text (initialize chunker with chunk_size)
        print("Step 2: Chunking text...")
        text_chunker = TextChunker(chunk_size=chunk_size)  # ← Initialize with chunk_size
        resume_chunks = text_chunker.chunk_text(resume_text)  # ← No parameter
        jd_chunks = text_chunker.chunk_text(jd_text)  # ← No parameter
        print(f"✓ Resume chunks: {len(resume_chunks)}")
        print(f"✓ JD chunks: {len(jd_chunks)}")
        
        if not resume_chunks or not jd_chunks:
            raise ValueError("Could not create chunks from PDFs")
        
        # Step 3: Generate embeddings
        print("Step 3: Generating embeddings...")
        resume_embeddings = embedding_gen.generate_embeddings_batch(resume_chunks)
        jd_embeddings = embedding_gen.generate_embeddings_batch(jd_chunks)
        print(f"✓ Embeddings generated")
        
        # Step 4: Calculate similarity
        print("Step 4: Computing similarity...")
        # Fallback to computing similarity directly on chunks if paths are None
        if resume_path and jd_path:
            similarity_score = analyze(str(resume_path), str(jd_path), chunk_size=chunk_size)
        else:
            # If input was text, we don't have files for `analyze()`, which expects file paths.
            # We can use the RAG pipeline or direct embeddings to compute similarity.
            # For simplicity, if text input is used, we compute a basic average similarity 
            # or just rely on RAG. Let's create dummy files for analyze if they don't exist.
            if not resume_path:
                resume_path = TEMP_DIR / "temp_resume.txt"
                with open(resume_path, "w", encoding="utf-8") as f:
                    f.write(resume_text)
            if not jd_path:
                jd_path = TEMP_DIR / "temp_jd.txt"
                with open(jd_path, "w", encoding="utf-8") as f:
                    f.write(jd_text)
            
            similarity_score = analyze(str(resume_path), str(jd_path), chunk_size=chunk_size)
            
        print(f"✓ Similarity score: {similarity_score:.4f}")
        
        # Determine match level
        if similarity_score >= 0.75:
            match_level = "Excellent"
        elif similarity_score >= 0.50:
            match_level = "Good"
        else:
            match_level = "Needs Improvement"
        
        result = {
            "success": True,
            "score": float(similarity_score),
            "score_percentage": f"{similarity_score * 100:.2f}%",
            "match_level": match_level,
            "analysis": {
                "raw_score": float(similarity_score),
                "percentage": similarity_score * 100,
                "chunk_size": chunk_size,
                "resume_chunks_count": len(resume_chunks),
                "jd_chunks_count": len(jd_chunks)
            },
            "interpretation": get_interpretation(similarity_score)
        }
        
        # Step 5: RAG evaluation (optional)
        if use_rag:
            try:
                print("Step 5: Running RAG...")
                embedding_dim = len(resume_embeddings[0]) if resume_embeddings else 384
                
                resume_store = VectorStore(dim=embedding_dim, use_faiss=True)
                jd_store = VectorStore(dim=embedding_dim, use_faiss=True)
                
                resume_store.add(resume_embeddings, resume_chunks)
                jd_store.add(jd_embeddings, jd_chunks)
                print("✓ Vector stores created")
                
                rag_pipeline = RAGPipeline(resume_store, jd_store, top_k=5)
                rag_result = rag_pipeline.run()
                print("✓ RAG pipeline executed")
                
                llm_response = call_llm(rag_result["prompt"])
                print("✓ LLM response received")
                
                result["rag_evaluation"] = {
                    "enabled": True,
                    "llm_response": llm_response,
                    "retrieved_resume_chunks": rag_result["resume_chunks"],
                    "retrieved_jd_chunks": rag_result["jd_chunks"],
                    "resume_relevance_scores": [float(s) for s in rag_result["resume_scores"]],
                    "jd_relevance_scores": [float(s) for s in rag_result["jd_scores"]]
                }
            except Exception as e:
                print(f"RAG error (non-fatal): {str(e)}")
                result["rag_evaluation"] = {
                    "enabled": False,
                    "error": str(e),
                    "note": "RAG failed, using similarity score only"
                }
        else:
            result["rag_evaluation"] = {"enabled": False}
        
        print("=" * 60)
        return JSONResponse(result)
    
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"error": str(e), "success": False},
            status_code=500
        )
    
    finally:
        if resume_path and resume_path.exists():
            resume_path.unlink()
        if jd_path and jd_path.exists():
            jd_path.unlink()


def get_interpretation(score: float) -> dict:
    """Get interpretation based on score"""
    if score >= 0.75:
        return {
            "level": "Excellent Match",
            "message": "Your resume is an excellent match for this job!",
            "recommendations": [
                "Your skills align well with the job requirements",
                "Proceed with confidence in your application",
                "Highlight strongest matches in cover letter"
            ]
        }
    elif score >= 0.50:
        return {
            "level": "Good Match",
            "message": "Your resume is a good match for this job.",
            "recommendations": [
                "Highlight relevant skills and experience",
                "Add more keywords from job description",
                "Emphasize matching accomplishments",
                "Use cover letter to explain fit"
            ]
        }
    else:
        return {
            "level": "Needs Improvement",
            "message": "Your resume may need some adjustments.",
            "recommendations": [
                "Identify key skills from job description",
                "Add or emphasize relevant experience",
                "Consider gaining required certifications",
                "Reorder resume to highlight relevant skills",
                "Ensure you have domain experience"
            ]
        }

@app.post("/chat")
async def chat_agent(request: ChatRequest):
    try:
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
        if request.current_latex:
            messages.append({"role": "system", "content": f"The user's current resume LaTeX code is:\n```latex\n{request.current_latex}\n```"})
            
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})
            
        response_text = call_llm_chat(messages, model="openai/gpt-4o-mini") # Use a good model for agent
        return {"response": response_text}
    except Exception as e:
        print(f"Chat error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/generate-latex")
async def generate_latex(request: GenerateLatexRequest):
    try:
        prompt = f"Resume Text:\n{request.resume_text}\n\nJob Description:\n{request.jd_text}\n\nGenerate the LaTeX resume now based on the system instructions."
        messages = [
            {"role": "system", "content": LATEX_GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        response_text = call_llm_chat(messages, model="openai/gpt-4o") # Use best model for generation
        
        # Clean up output to just be the latex
        latex = response_text
        if "```latex" in latex:
            latex = latex.split("```latex")[1].split("```")[0].strip()
        elif "```" in latex:
            latex = latex.split("```")[1].split("```")[0].strip()
            
        return {"latex": latex}
    except Exception as e:
        print(f"Generate latex error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

import background_tasks
from fastapi import BackgroundTasks

@app.post("/compile-latex")
async def compile_latex(request: CompileLatexRequest, background_tasks: BackgroundTasks):
    try:
        pdf_path = latex_engine.compile_latex(request.latex_content)
        # Clean up the folder after sending
        background_tasks.add_task(latex_engine.cleanup, pdf_path)
        return FileResponse(pdf_path, media_type="application/pdf", filename="resume.pdf")
    except Exception as e:
        print(f"Compile latex error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    print("Starting server...")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
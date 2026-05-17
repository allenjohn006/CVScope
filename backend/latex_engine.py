import os
import subprocess
import tempfile
import uuid
from pathlib import Path

class LatexEngine:
    def __init__(self, temp_dir="temp_latex"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        
    def compile_latex(self, latex_content: str) -> str:
        """
        Compiles LaTeX string to PDF and returns the path to the generated PDF.
        """
        job_id = str(uuid.uuid4())
        job_dir = self.temp_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        tex_file_path = job_dir / "resume.tex"
        with open(tex_file_path, "w", encoding="utf-8") as f:
            f.write(latex_content)
            
        try:
            # Run pdflatex twice for cross-references, though usually once is enough for simple resumes
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "resume.tex"],
                cwd=str(job_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30 # 30 seconds timeout
            )
            
            if result.returncode != 0:
                print(f"LaTeX Compilation Error:\n{result.stdout}\n{result.stderr}")
                raise Exception("LaTeX compilation failed. Check logs for details.")
                
            pdf_path = job_dir / "resume.pdf"
            if not pdf_path.exists():
                raise Exception("PDF file was not generated.")
                
            return str(pdf_path)
            
        except subprocess.TimeoutExpired:
            raise Exception("LaTeX compilation timed out.")
        except FileNotFoundError:
            raise Exception("pdflatex command not found. Please ensure a LaTeX distribution is installed.")
        except Exception as e:
            raise Exception(f"Failed to compile LaTeX: {str(e)}")

    def cleanup(self, pdf_path: str):
        """
        Clean up the temporary directory associated with the pdf path.
        """
        try:
            job_dir = Path(pdf_path).parent
            if job_dir.exists() and job_dir.is_dir() and job_dir.parent.name == self.temp_dir.name:
                import shutil
                shutil.rmtree(job_dir)
        except Exception as e:
            print(f"Failed to cleanup {pdf_path}: {e}")

latex_engine = LatexEngine()

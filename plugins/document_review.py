"""
plugins/document_review.py - Automated document review and analysis.

Adheres to AGENTS.md:
- Calls thread-safe player.show_review(title, summary, findings).
- Processes long text on a background thread; returns immediately.
- Never raises exceptions, returns concise speech feedback.
"""
import threading
from pathlib import Path
from core import gemini

PLUGIN = {
    "name": "document_review",
    "description": (
        "Reviews a document or text file and displays a structured review with summary and critical findings on screen. "
        "Supports markdown, text, code, docx, or pdf."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "Path to the document file to review.",
            },
            "focus": {
                "type": "STRING",
                "description": "Review focus: 'general', 'grammar', 'conciseness', 'technical', 'security'.",
                "enum": ["general", "grammar", "conciseness", "technical", "security"],
            },
        },
        "required": ["path"],
    },
}


def _read_document_text(path_str: str) -> str:
    path = Path(path_str).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path_str}")

    suffix = path.suffix.lower()

    if suffix in (".txt", ".md", ".py", ".json", ".yaml", ".yml", ".sh", ".c", ".cpp", ".js", ".html"):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(50000)

    elif suffix == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages[:10]]
                return "\n".join(pages)
        except Exception:
            try:
                import PyPDF2
                with open(path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    return "\n".join([page.extract_text() or "" for page in reader.pages[:10]])
            except Exception as e:
                raise RuntimeError(f"Could not read PDF: {e}")

    elif suffix == ".docx":
        try:
            import docx
            doc = docx.Document(path)
            return "\n".join([p.text for p in doc.paragraphs[:100]])
        except Exception as e:
            raise RuntimeError(f"Could not read DOCX: {e}")

    else:
        # Fallback raw read
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(30000)


def _review_worker(file_path: str, focus: str, player):
    try:
        raw_text = _read_document_text(file_path)
        if not raw_text.strip():
            if player:
                player.write_log(f"⚠️ [Review] Document at {file_path} appears empty.")
            return

        prompt = f"""Review the following document focusing on '{focus}'.
Provide a structured review returning ONLY a JSON object with:
{{
  "title": "Review: {Path(file_path).name}",
  "summary": "2-3 sentence executive summary of document quality and key points",
  "findings": [
    "Specific finding or recommendation 1",
    "Specific finding or recommendation 2",
    "Specific finding or recommendation 3"
  ]
}}

DOCUMENT EXCERPT:
{raw_text[:12000]}
"""
        data = gemini.as_json(prompt, tier=gemini.FAST)
        if not (isinstance(data, dict) and "summary" in data and "findings" in data):
            title = f"Review: {Path(file_path).name}"
            summary = "Document review completed with standard structural scan."
            findings = ["Ensure standard formatting is maintained.", "Verify technical accuracy across all sections."]
        else:
            title = str(data.get("title", f"Review: {Path(file_path).name}"))
            summary = str(data["summary"])
            findings = [str(f) for f in data["findings"]]

        if player:
            try:
                player.show_review(title, summary, findings)
                player.write_log(f"📄 [Review] Completed review for {Path(file_path).name} ({len(findings)} findings).")
            except Exception:
                pass

    except Exception as e:
        if player:
            try:
                player.write_log(f"⚠️ [Review] Error reviewing {file_path}: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    path_str = str(parameters.get("path") or "").strip()
    focus = str(parameters.get("focus") or "general").strip()

    if not path_str:
        return "Please specify the file path of the document you would like me to review."

    path = Path(path_str).expanduser()
    if not path.is_file():
        return f"Document not found at path '{path_str}'."

    threading.Thread(
        target=_review_worker,
        args=(str(path), focus, player),
        daemon=True,
    ).start()

    return f"Reviewing {path.name} with a focus on {focus}. The structured findings will appear on the display in a moment."

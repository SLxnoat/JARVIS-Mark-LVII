"""
plugins/quiz.py - Spoken & interactive quiz generator.

Adheres strictly to AGENTS.md:
- Calls thread-safe player.show_quiz(topic, questions, grade=None).
- Uses core.gemini.as_json() with fast fallback.
- Returns immediately with a short spoken announcement while user answers on screen.
"""
import threading
from core import gemini

PLUGIN = {
    "name": "quiz",
    "description": (
        "Generates an interactive multiple-choice quiz on any topic and displays it on the screen. "
        "The user answers directly on the HUD."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "topic": {
                "type": "STRING",
                "description": "Topic of the quiz, e.g. 'Python Programming', 'World History', 'Quantum Physics'.",
            },
            "num_questions": {
                "type": "INTEGER",
                "description": "Number of questions to generate (default 3, max 5).",
            },
            "difficulty": {
                "type": "STRING",
                "description": "Difficulty level: 'easy', 'medium', or 'hard'.",
                "enum": ["easy", "medium", "hard"],
            },
        },
        "required": ["topic"],
    },
}


def _generate_questions(topic: str, num_q: int, difficulty: str) -> list[dict]:
    prompt = f"""Generate an interactive multiple choice quiz with exactly {num_q} questions on the topic '{topic}' with difficulty '{difficulty}'.
Return ONLY a JSON array of objects with the following schema:
[
  {{
    "question": "Clear question text?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Exact matching string from options",
    "note": "Short explanatory note shown after answering"
  }}
]
"""
    try:
        data = gemini.as_json(prompt, tier=gemini.FAST)
        if isinstance(data, list) and len(data) > 0:
            valid_questions = []
            for item in data:
                if isinstance(item, dict) and "question" in item and "options" in item and "answer" in item:
                    valid_questions.append({
                        "question": str(item["question"]),
                        "options": [str(opt) for opt in item["options"]],
                        "answer": str(item["answer"]),
                        "note": str(item.get("note", "")),
                    })
            if valid_questions:
                return valid_questions[:num_q]
    except Exception:
        pass

    # Built-in fallback
    return [
        {
            "question": f"Which of the following is most closely associated with {topic}?",
            "options": ["Fundamental Principles", "External Noise", "Irrelevant Factors", "Random Static"],
            "answer": "Fundamental Principles",
            "note": f"Understanding fundamental principles is central to {topic}.",
        }
    ]


def run(parameters: dict, player=None, session_memory=None) -> str:
    topic = str(parameters.get("topic") or "General Knowledge").strip()
    raw_num = parameters.get("num_questions") or parameters.get("questions_count") or parameters.get("count") or 3
    num_q = max(1, min(int(raw_num), 5))
    difficulty = str(parameters.get("difficulty") or "medium").strip()

    if not player:
        return f"Prepared a quiz on {topic}, but no visual display is available."

    def _worker():
        try:
            questions = _generate_questions(topic, num_q, difficulty)
            player.show_quiz(topic=topic, questions=questions, grade=None)
            player.write_log(f"[Quiz] Generated {len(questions)} question(s) on '{topic}' ({difficulty}).")
        except Exception as e:
            try:
                player.write_log(f"[Quiz] Failed to launch quiz: {e}")
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()
    return f"I've prepared a {difficulty} quiz on {topic} with {num_q} questions. Take a look at the screen to answer!"

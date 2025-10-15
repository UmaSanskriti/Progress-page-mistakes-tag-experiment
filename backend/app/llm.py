from __future__ import annotations

import os
import textwrap


def _render_prompt(
    *,
    question: str,
    reference_answer: str,
    student_answer: str,
    mark_available: float,
    mark_awarded: float,
) -> str:
    question = question.strip() or "(question text unavailable)"
    reference_answer = reference_answer.strip() or "(reference answer unavailable)"
    student_answer = student_answer.strip() or "(student answer unavailable)"
    return textwrap.dedent(
        f"""
        Review the student's response to a question and summarise the mistake as a short category.

        - Provide only the category text with no explanations.
        - The category must be one to three words.
        - Use specific science or maths vocabulary when it helps describe the misunderstanding.
        - If the student response is effectively correct, answer with "Correct".

        Question: {question}
        Reference answer: {reference_answer}
        Student answer: {student_answer}
        Mark available: {mark_available}
        Mark awarded: {mark_awarded}
        """
    ).strip()


class OpenAIMistakeCategoryClient:
    """LLM client that asks OpenAI to summarise mistakes."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except Exception as exc:  # pragma: no cover - import error paths are environment specific
                raise RuntimeError("openai package is not installed") from exc
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def generate_category(
        self,
        *,
        question: str,
        reference_answer: str,
        student_answer: str,
        mark_available: float,
        mark_awarded: float,
    ) -> str:
        client = self._ensure_client()
        prompt = _render_prompt(
            question=question,
            reference_answer=reference_answer,
            student_answer=student_answer,
            mark_available=mark_available,
            mark_awarded=mark_awarded,
        )
        response = client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": "You assign concise mistake categories for student answers.",
                },
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=50,
        )
        return getattr(response, "output_text", "").strip()

    @classmethod
    def from_env(cls) -> "OpenAIMistakeCategoryClient | None":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        model = os.getenv("OPENAI_MODEL")
        return cls(api_key=api_key, model=model)


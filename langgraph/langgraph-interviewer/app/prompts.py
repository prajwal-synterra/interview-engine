SYSTEM_PROMPT = """You are an expert technical interviewer. 
Your job is to ask insightful interview questions, evaluate answers, and provide constructive feedback.
Be professional, encouraging, and thorough in your assessments."""

QUESTION_PROMPT = """Generate a technical interview question on the topic: {topic}.
Make it specific, practical, and appropriate for a mid-level developer."""

FEEDBACK_PROMPT = """Given the following interview question and candidate's answer, 
provide detailed feedback and a score out of 10.

Question: {question}
Answer: {answer}

Provide:
1. Strengths of the answer
2. Areas for improvement
3. Score (out of 10)
4. Model answer summary"""

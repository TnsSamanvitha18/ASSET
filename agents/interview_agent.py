from google import genai
import json
# REPLACE IT WITH GOOGLE GEMINI API KEY
client = genai.Client(api_key="AIxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") 

def generate_batch(candidates_data, jd_text):
    """
    Generates interview questions for a batch of candidates in one call.
    candidates_data: list of dicts [{'id': '...', 'skills': '...'}, ...]
    jd_text: The job description text.
    Returns a list of structured JSON objects.
    """
    if not candidates_data:
        return []

    # Format candidate info for the prompt
    candidates_info = "\n".join([
        f"Candidate ID: {c['id']}\nSkills: {c['skills']}\n---" 
        for c in candidates_data
    ])

    prompt = f"""
    You are an expert technical interviewer. Generate tailored interview questions for the following candidates based on their skills and the provided job description.

    Job Description:
    {jd_text}

    Candidates:
    {candidates_info}

    Task:
    For EACH candidate, generate 3-5 questions per category:
    1. Technical: Focused on the candidate's specific skills and how they apply to the JD.
    2. HR: Behavioral and situational questions.
    3. Cultural Fit: Questions to assess alignment with the company and role.

    Return the response as a JSON ARRAY of objects, one for each candidate, with this exact structure:
    [
      {{
        "candidate_id": "...",
        "questions": {{
          "technical": ["Q1", "Q2", "Q3", ...],
          "hr": ["Q1", "Q2", "Q3", ...],
          "cultural_fit": ["Q1", "Q2", "Q3", ...]
        }}
      }},
      ...
    ]
    """

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )

    # Clean up response text if it contains markdown code blocks
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        results = json.loads(text)
        if not isinstance(results, list):
            results = [results]
        return results
    except json.JSONDecodeError:
        # Fallback if JSON parsing fails - return minimal questions for each candidate
        fallback_results = []
        for c in candidates_data:
            fallback_results.append({
                "candidate_id": c['id'],
                "questions": {
                    "technical": [f"Could you explain your experience with {c['skills'].split(',')[0] if c['skills'] else 'the required skills'}?"],
                    "hr": ["Why are you interested in this position?"],
                    "cultural_fit": ["How do you handle working in a fast-paced environment?"]
                }
            })
        return fallback_results

def generate(candidate_id, skills, jd_text):
    """
    Legacy single-candidate wrapper for backward compatibility.
    """
    results = generate_batch([{"id": candidate_id, "skills": skills}], jd_text)
    return results[0] if results else None

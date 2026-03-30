from google import genai

# REPLACE IT WITH GOOGLE GEMINI API KEY
client = genai.Client(api_key="AIxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") 



def find_match(resume_data, jd_text):
    prompt = f"""
    Analyze the following job description and resumes.
    
    Job Description:
    {jd_text}

    Resumes:
    {resume_data}

    Tasks:
    1. Create a short, descriptive title for this Job Description (e.g., "Senior Python Developer", "Marketing Manager").
    2. Compare each resume with the job description.

    Return the results as a JSON object with the following structure:
    {{
        "jd_title": "<short descriptive title>",
        "matches": [
            {{
                "name": "<candidate name>",
                "file_name": "<file name associated with the resume>",
                "email": "<candidate email>",
                "score": <match score from 0-100>,
                "skills": "<suitable skills found in the resume matching the JD as a single string>",
                "role": "<role specialization>",
                "justification": "<1 line explaining why the candidate is suitable>"
            }},
            ...
        ]
    }}

    Ensure the response is a valid JSON object.
    """

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )

    return response.text


def calculate_match(resume_text, jd_text):
    prompt = f"""
    Compare the following resume with the job description.

    Resume:
    {resume_text}

    Job Description:
    {jd_text}

    Return:
    1. Match score (0-100)
    2. Short justification (1 line explaining why the candidate is suitable)

    Format as a JSON object with keys "score" and "justification".
    """

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )

    return response.text

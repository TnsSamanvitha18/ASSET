import os
from google import genai
import pdfplumber
# REPLACE IT WITH GOOGLE GEMINI API KEY
client = genai.Client(api_key="AIxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") 


def extract_skills(resume_path):
    if resume_path.endswith(".pdf"):
        text = ""
        with pdfplumber.open(resume_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        resume_text = text

    else:  # txt file
        with open(resume_path, "r") as f:
            resume_text = f.read()

    prompt = f"""
    Analyze the following resume:
    
    Resume:
    {resume_text}

    Task:
    1. Extract the Skills of the candidate as a comma-separated list.
    2. Identify the candidate's most suitable specialization/role (e.g., Python Developer, HR, Team Leader, Data Analyst).

    Return your response in the format:
    Skills: <comma separated values>
    Role: <specialization>
    """

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )

    # Parsing skills and role from response
    skills = ""
    role = "Not Identified"
    
    lines = [line.strip() for line in response.text.split("\n") if line.strip()]
    for line in lines:
        if line.lower().startswith("skills:"):
            skills = line.replace("Skills:", "").replace("skills:", "").strip()
        elif line.lower().startswith("role:"):
            role = line.replace("Role:", "").replace("role:", "").strip()

    return resume_text, skills, role

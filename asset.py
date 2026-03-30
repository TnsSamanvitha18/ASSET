from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import os
import json
import uuid
from werkzeug.utils import secure_filename

# Import from agents
from agents.match_agent import find_match
from agents.skill_agent import extract_skills
from agents import interview_agent

app = Flask(__name__)
app.secret_key = "super_secret_key" # Added for session storage of JD

RESUME_FOLDER = "resumes"
CANDIDATES_JSON = "candidates.json"
SHORTLIST_JSON = "short_list.json"
ALLOWED_EXTENSIONS = {'pdf'}

if not os.path.exists(RESUME_FOLDER):
    os.makedirs(RESUME_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_candidates():
    if not os.path.exists(CANDIDATES_JSON):
        return []
    with open(CANDIDATES_JSON, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            return data["resumes"] if isinstance(data, dict) and "resumes" in data else data
        except json.JSONDecodeError:
            return []

def save_candidates(candidates_list):
    with open(CANDIDATES_JSON, 'w', encoding='utf-8') as f:
        json.dump(candidates_list, f, indent=4)

def load_shortlist():
    if not os.path.exists(SHORTLIST_JSON):
        return []
    with open(SHORTLIST_JSON, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_shortlist(shortlist_data):
    with open(SHORTLIST_JSON, 'w', encoding='utf-8') as f:
        json.dump(shortlist_data, f, indent=4)

def run_pipeline(stage, **kwargs):
    """
    Orchestrates the agentic pipeline. 
    Stages: 'extract', 'match', 'interview'
    """
    if stage == 'extract':
        file_path = kwargs.get('file_path')
        return extract_skills(file_path)
    
    elif stage == 'match':
        all_resume_texts = kwargs.get('all_resume_texts')
        jd_text = kwargs.get('jd_text')
        result = find_match(all_resume_texts, jd_text)
        # Clean up JSON from LLM
        result = result.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return []
            
    elif stage == 'interview':
        # Now handles a batch of candidates
        candidates_data = kwargs.get('candidates_data') # list of {'id': ..., 'skills': ...}
        jd_text = kwargs.get('jd_text')
        return interview_agent.generate_batch(candidates_data, jd_text)
    
    return None

INTERVIEWER_CREDENTIALS = {"username": "admin", "password": "admin"}

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        email = request.form.get("email")
        name = request.form.get("name", "Unknown")
        file = request.files.get("resume")

        if file and allowed_file(file.filename):
            unique_id = str(uuid.uuid4())[:8]
            filename = secure_filename(f"{unique_id}_{file.filename}")
            file_path = os.path.join(RESUME_FOLDER, filename)
            file.save(file_path)

            # Use pipeline for extraction
            resume_text, skills, role = run_pipeline('extract', file_path=file_path)

            candidates = load_candidates()
            new_candidate = {
                "id": unique_id,
                "file_name": filename,
                "email": email,
                "name": name,
                "skills": skills,
                "role": role,
                "resume_text": resume_text,
                "status": "pending",
                "scores": {},
                "rejection_reason": None
            }
            candidates.append(new_candidate)
            save_candidates(candidates)

            return render_template("index.html", success="Resume uploaded successfully!", active_tab='candidate')
        
        return render_template("index.html", error="Invalid file format. Please upload a PDF.", active_tab='candidate')

    return render_template("index.html", active_tab='candidate')

@app.route("/login", methods=["GET", "POST"])
def recruiter_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "admin":
            session['recruiter_logged_in'] = True
            return redirect(url_for('recruiter_dashboard'))
        else:
            return render_template("login.html", error="Invalid credentials", active_tab='recruiter')
    return render_template("login.html", active_tab='recruiter')

@app.route("/interviewer/login", methods=["GET", "POST"])
def interviewer_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == INTERVIEWER_CREDENTIALS["username"] and password == INTERVIEWER_CREDENTIALS["password"]:
            session['interviewer_logged_in'] = True
            return redirect(url_for('interviewer'))
        else:
            return render_template("interviewer_login.html", error="Invalid credentials", active_tab='interviewer')
    return render_template("interviewer_login.html", active_tab='interviewer')

@app.route("/interviewer/logout")
def interviewer_logout():
    session.pop('interviewer_logged_in', None)
    return redirect(url_for('interviewer_login'))

@app.route("/dashboard", methods=["GET", "POST"])
def recruiter_dashboard():
    if not session.get('recruiter_logged_in'):
        return redirect(url_for('recruiter_login'))
    
    candidates = load_candidates()

    if request.method == "POST":
        jd = request.form.get("jd")
        session['current_jd'] = jd
        session['active_jd_id'] = str(uuid.uuid4())
        
        # Clean slate: Reset all candidates for the new JD session
        for cand in candidates:
            cand['score'] = None
            cand['matched_skills'] = []
            cand['justification'] = "Pending analysis"
            cand['status'] = 'pending'
            cand['shortlisted_jd_id'] = None
            cand['rejection_reason'] = None
            cand['scores'] = {}
            
        # Prepare candidate data for the match agent
        # Including identifiers (file_name, email) so the agent can return them back for linking
        candidate_data_for_match = [
            {
                "file_name": c.get("file_name"),
                "email": c.get("email"),
                "name": c.get("name"),
                "resume_text": c.get("resume_text", "")
            }
            for c in candidates
        ]
        
        # Use pipeline for matching
        match_data = run_pipeline('match', all_resume_texts=json.dumps(candidate_data_for_match), jd_text=jd)
        jd_title = match_data.get("jd_title", "Unknown Job Description")
        match_results = match_data.get("matches", [])
        
        session['active_jd_id'] = f"{jd_title}_{str(uuid.uuid4())[:8]}"
        
        # Update local candidates list with match results for display
        for match in match_results:
            # Try to link match result back to candidate by file_name or email
            for cand in candidates:
                if cand.get("file_name") == match.get("file_name") or cand.get("email") == match.get("email"):
                    cand.update({
                        "score": match.get("score"),
                        "matched_skills": match.get("skills"),
                        "justification": match.get("justification")
                    })
                    break
        save_candidates(candidates)
        return redirect(url_for('recruiter_dashboard'))
    
    # On GET, show all candidates
    results = candidates
    rejected = [c for c in candidates if c.get('status') == 'rejected']

    return render_template("dashboard.html", results=results, rejected=rejected, active_tab='recruiter')

@app.route("/shortlist", methods=["POST"])
def shortlist():
    candidate_ids = request.form.getlist("candidate_ids")
    candidates = load_candidates()
    shortlist_data = load_shortlist()
    jd_text = session.get('current_jd', "")
    active_jd_id = session.get('active_jd_id', "unknown_jd")

    # Find or create JD entry
    jd_entry = next((item for item in shortlist_data if item["jd_id"] == active_jd_id), None)
    if not jd_entry:
        jd_entry = {"jd_id": active_jd_id, "shortlist": []}
        shortlist_data.append(jd_entry)

    # Identify candidates needing interview questions
    to_batch = []
    for cand in candidates:
        if cand['id'] in candidate_ids:
            cand['status'] = 'shortlisted'
            cand['shortlisted_jd_id'] = active_jd_id
            
            # Check if questions already exist in jd_entry
            existing_questions = next((c for c in jd_entry["shortlist"] if c["candidate_id"] == cand["id"]), None)
            if not existing_questions:
                to_batch.append({"id": cand['id'], "skills": cand['skills']})
    
    # Run batch generation once
    if to_batch:
        batch_results = run_pipeline('interview', 
                                   candidates_data=to_batch, 
                                   jd_text=jd_text)
        
        # Add generated questions to jd_entry
        for res in batch_results:
            jd_entry["shortlist"].append({
                "candidate_id": res['candidate_id'],
                "questions": res['questions']
            })
    
    save_candidates(candidates)
    save_shortlist(shortlist_data)
    return redirect(url_for('recruiter_dashboard'))

@app.route("/reject", methods=["POST"])
def reject():
    candidate_ids = request.form.getlist("candidate_ids")
    candidates = load_candidates()

    for cand in candidates:
        if cand['id'] in candidate_ids:
            cand['status'] = 'rejected'
            # Reason is derived from the match agent's justification
            cand['rejection_reason'] = cand.get('justification', "No justification provided by AI.")
    
    save_candidates(candidates)
    return redirect(url_for('recruiter_dashboard'))

@app.route("/interviewer")
def interviewer():
    if not session.get('interviewer_logged_in'):
        return redirect(url_for('interviewer_login'))

    shortlist_data = load_shortlist()
    jd_id = request.args.get('jd_id')

    if not jd_id:
        # Show selection list
        return render_template("interviewer.html", jd_list=shortlist_data, active_tab='interviewer')

    # Show details for specific JD
    jd_entry = next((item for item in shortlist_data if item["jd_id"] == jd_id), None)
    if not jd_entry:
        return redirect(url_for('interviewer'))

    candidates = load_candidates()
    shortlisted = []
    
    for item in jd_entry["shortlist"]:
        cand = next((c for c in candidates if c["id"] == item["candidate_id"]), None)
        if cand:
            # Attach questions from shortlist_data
            cand['interview_data'] = {"questions": item["questions"]}
            shortlisted.append(cand)
            
    return render_template("interviewer.html", shortlisted=shortlisted, jd_id=jd_id, active_tab='interviewer')

@app.route("/save_scores", methods=["POST"])
def save_scores():
    if not session.get('interviewer_logged_in'):
        return redirect(url_for('interviewer_login'))
    
    candidate_id = request.form.get("candidate_id")
    jd_id = request.form.get("jd_id")
    tech_score = int(request.form.get("tech_score", 0))
    hr_score = int(request.form.get("hr_score", 0))
    culture_score = int(request.form.get("culture_score", 0))
    
    candidates = load_candidates()
    for cand in candidates:
        if cand['id'] == candidate_id:
            cand['scores'] = {
                "technical": tech_score,
                "hr": hr_score,
                "cultural_fit": culture_score,
                "average": round((tech_score + hr_score + culture_score) / 3, 2)
            }
            break
            
    save_candidates(candidates)
    return redirect(url_for('interviewer', jd_id=jd_id))

@app.route("/logout")
def logout():
    session.pop('recruiter_logged_in', None)
    session.pop('current_jd', None)
    return redirect(url_for('recruiter_login'))

if __name__ == "__main__":
    app.run(debug=True)

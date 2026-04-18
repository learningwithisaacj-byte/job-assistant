# ================== IMPORTS ==================
import streamlit as st
import sqlite3
import os
import re
import pandas as pd
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
import requests
from bs4 import BeautifulSoup

st.set_page_config(layout="wide")

# ================== DB SETUP ==================
conn = sqlite3.connect("jobs.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    resume TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS applications (
    username TEXT,
    title TEXT,
    company TEXT,
    status TEXT,
    notes TEXT,
    PRIMARY KEY(username, title, company)
)
""")

conn.commit()

# ================== USER LOGIN ==================
st.sidebar.title("👤 User")
username = st.sidebar.text_input("Enter Username")

if not username:
    st.stop()

c.execute("INSERT OR IGNORE INTO users (username, resume) VALUES (?, ?)", (username, ""))
conn.commit()

# ================== RESUME EDITOR ==================
st.sidebar.subheader("📄 Resume Editor")

c.execute("SELECT resume FROM users WHERE username=?", (username,))
resume_data = c.fetchone()[0]

resume_text = st.sidebar.text_area("Edit Resume", value=resume_data, height=300)

if st.sidebar.button("💾 Save Resume"):
    c.execute("UPDATE users SET resume=? WHERE username=?", (resume_text, username))
    conn.commit()
    st.sidebar.success("Saved!")

# ================== HELPERS ==================
COMMON_SKILLS = ["agile","scrum","safe","jira","stakeholder","delivery"]

def extract_keywords(desc):
    return [k.capitalize() for k in COMMON_SKILLS if k in desc.lower()]

def rewrite_bullet(line):
    line = line.lower().replace("responsible for","").strip()
    if "manage" in line:
        return "Managed " + line.replace("manage","").strip()
    if "lead" in line:
        return "Led " + line.replace("lead","").strip()
    if "deliver" in line:
        return "Delivered " + line.replace("deliver","").strip()
    return line.capitalize()

def calculate_ats(desc, resume):
    d = set(re.findall(r'\w+', desc.lower()))
    r = set(re.findall(r'\w+', resume.lower()))
    if not d: return 0
    return min(int(len(d & r)/len(d)*100), 92)

def improve_resume(desc, resume):
    d = set(re.findall(r'\w+', desc.lower()))
    r = set(re.findall(r'\w+', resume.lower()))
    missing = [w for w in d-r if len(w)>4][:8]
    if not missing: return resume
    return resume + "\n\nADDITIONAL SKILLS\n" + ", ".join(missing)

def generate_resume(title, company, desc, base):
    skills = ", ".join(extract_keywords(desc))

    bullets = []
    for line in desc.split("\n")[:10]:
        if len(line)>40:
            bullets.append(rewrite_bullet(line))

    if len(bullets)<3:
        bullets += [
            "Led Agile teams delivering enterprise solutions",
            "Improved delivery timelines and stakeholder alignment"
        ]

    exp = "\n".join([f"- {b}" for b in bullets[:5]])

    return f"""
{username.upper()}
Email: your@email.com | India

{title.upper()}

SUMMARY
Experienced professional aligned to {title} at {company}.

SKILLS
{skills}

EXPERIENCE
{exp}

TOOLS
Jira, Confluence

EDUCATION
MBA
"""

def save_pdf(file, text):
    doc = SimpleDocTemplate(file)
    style = ParagraphStyle(name="Normal", fontSize=10)

    content = []
    for line in text.split("\n"):
        if line.strip():
            content.append(Paragraph(line, style))
            content.append(Spacer(1,5))

    doc.build(content)

# ================== JOB SEARCH ==================
st.title("🚀 AI Job Assistant")

role = st.text_input("🔍 Search Role", "Scrum Master")

def search_jobs(role):
    url = f"https://www.google.com/search?q={role}+jobs"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    jobs = []
    for g in soup.find_all("h3")[:5]:
        jobs.append({
            "title": g.text,
            "company": "Company",
            "link": "https://www.google.com"
        })
    return jobs

if st.button("Search Jobs"):
    st.session_state.jobs = search_jobs(role)

# ================== DISPLAY JOBS ==================
if "jobs" in st.session_state:

    for i, job in enumerate(st.session_state.jobs):

        st.subheader(job["title"])
        st.write(job["company"])

        desc = job["title"] + " Agile Scrum stakeholder delivery"

        resume = generate_resume(job["title"], job["company"], desc, resume_text)
        score = calculate_ats(desc, resume)

        if score < 80:
            resume = improve_resume(desc, resume)
            score = calculate_ats(desc, resume)

        st.write(f"📊 ATS Score: {score}%")

        with st.expander("📄 View Resume"):
            st.text(resume)

        pdf_file = f"{username}_{i}.pdf"
        save_pdf(pdf_file, resume)

        with open(pdf_file, "rb") as f:
            st.download_button("⬇ Download Resume", f, file_name=pdf_file)

        st.link_button("Apply 🔗", job["link"])

        # -------- TRACKING --------
        status = st.selectbox("Status", ["Saved","Applied","Interview","Offer","Rejected"], key=i)
        notes = st.text_input("Notes", key=f"n{i}")

        if st.button("Save", key=f"s{i}"):
            c.execute("""
            INSERT OR REPLACE INTO applications VALUES (?,?,?,?,?)
            """, (username, job["title"], job["company"], status, notes))
            conn.commit()
            st.success("Updated")

        st.divider()
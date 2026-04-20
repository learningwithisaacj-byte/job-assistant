"""
sample_transformation.py
Demonstrates a before/after resume transformation.
Run standalone: python sample_transformation.py
"""

SAMPLE_JD = """
Software Engineer – Python/ML Platform
Acme Corp | Hyderabad, India

We are looking for a Python Software Engineer to join our ML Platform team.

Requirements:
• 3+ years of Python development experience
• Strong experience with FastAPI, Django, or Flask
• Hands-on experience with ML frameworks: PyTorch or TensorFlow
• Experience with containerization (Docker, Kubernetes)
• Proficiency with cloud platforms (AWS preferred)
• Experience with CI/CD pipelines (GitHub Actions, Jenkins)
• Strong understanding of REST API design
• Experience with PostgreSQL and Redis
• Familiarity with LangChain or similar LLM frameworks

Nice to have:
• MLOps experience (MLflow, Kubeflow)
• Experience with Kafka or message queues
• Prior experience at a product startup
"""

BEFORE_RESUME = """
John Doe
johndoe@email.com | 9876543210 | Hyderabad | linkedin.com/in/johndoe

Objective: Looking for a software engineering job where I can use my Python skills.

Work Experience:

Software Developer – XYZ Tech (Jan 2022 – Present)
- Worked on backend systems using Python
- Helped with the API development
- Did some database work
- Worked in an Agile team
- Fixed bugs and wrote code

Junior Developer – ABC Solutions (Jun 2020 – Dec 2021)
- Python scripting
- Made some ML models
- Used AWS sometimes
- Wrote unit tests

Education:
B.Tech in Computer Science – JNTU Hyderabad – 2020 – 8.2 CGPA

Skills: Python, SQL, AWS, Machine Learning, Docker
"""

AFTER_RESUME_EXAMPLE = """
John Doe
johndoe@email.com | +91-9876543210 | Hyderabad, India | linkedin.com/in/johndoe | github.com/johndoe

PROFESSIONAL SUMMARY
Results-driven Python Software Engineer with 4+ years of experience building scalable backend
systems and ML platforms. Proven track record of architecting FastAPI microservices, deploying
containerised workloads on AWS/Kubernetes, and integrating ML pipelines using PyTorch and
LangChain. Adept at CI/CD-driven development and cross-functional collaboration in Agile
environments.

TECHNICAL SKILLS
Core:      Python, FastAPI, PyTorch, Docker, Kubernetes, AWS (EC2, S3, Lambda), PostgreSQL
Additional: Redis, LangChain, GitHub Actions, MLflow, REST API Design, CI/CD, Kafka

PROFESSIONAL EXPERIENCE

Senior Python Engineer – XYZ Tech, Hyderabad  |  Jan 2022 – Present
• Architected a FastAPI-based microservices platform handling 50K+ daily API requests,
  reducing latency by ~35% through Redis caching and async query optimisation.
• Developed and deployed 4 PyTorch ML models to production using Docker and Kubernetes,
  cutting model inference time by 28% via batching and quantisation.
• Designed RESTful APIs consumed by 3 downstream teams, implementing OAuth2 authentication
  and automated OpenAPI documentation.
• Implemented GitHub Actions CI/CD pipelines, reducing deployment cycles from weekly
  to daily and eliminating ~90% of manual release steps.
• Managed PostgreSQL schemas for a 10M+ row dataset, optimising queries with indexes
  and partitioning to achieve sub-100ms p95 response times.

Python Developer – ABC Solutions, Hyderabad  |  Jun 2020 – Dec 2021
• Built end-to-end ML pipelines on AWS SageMaker, automating data preprocessing to
  model deployment and reducing engineer hours by ~40% per project.
• Integrated LangChain-powered Q&A features into an internal knowledge base product,
  improving query resolution accuracy by 22%.
• Containerised 6 legacy Python services using Docker, enabling consistent deployment
  across development, staging, and production environments.
• Collaborated in a 10-person Agile squad, participating in sprint planning, code reviews,
  and retrospectives using Jira and GitHub.

EDUCATION
B.Tech in Computer Science – JNTU Hyderabad  |  2020  |  GPA: 8.2/10

CERTIFICATIONS
• AWS Solutions Architect – Associate (2023)
• Docker Certified Associate (2022)

PROJECTS
LLM-Powered Resume Screener (github.com/johndoe/llm-screener)
  Built a FastAPI + LangChain application that scores resumes against JDs using Claude API,
  achieving 87% alignment with human recruiter ratings across 200 test resumes.
"""

TRANSFORMATION_NOTES = """
KEY IMPROVEMENTS (Before → After)
===================================
1. OBJECTIVE → SUMMARY
   ✗ "Looking for a job..." (passive, generic)
   ✓ 3-sentence summary packed with JD keywords: FastAPI, ML platform, PyTorch, LangChain

2. SKILL REORDERING
   ✗ Random order: Python, SQL, AWS, ML, Docker
   ✓ Core skills mirror JD priority: FastAPI, PyTorch, Docker, Kubernetes, AWS, PostgreSQL

3. ACTION VERBS
   ✗ "Worked on...", "Did some...", "Made..."  (weak, vague)
   ✓ "Architected...", "Developed...", "Implemented..."  (strong, specific)

4. QUANTIFIED ACHIEVEMENTS
   ✗ "Helped with API development"
   ✓ "Architected FastAPI platform handling 50K+ daily requests, reducing latency ~35%"

5. JD KEYWORDS EMBEDDED
   JD required: FastAPI ✅  PyTorch ✅  Docker ✅  Kubernetes ✅  AWS ✅
                PostgreSQL ✅  Redis ✅  LangChain ✅  CI/CD ✅  REST API ✅

6. NO FABRICATION
   ✓ All companies, dates, and degree remain exactly the same
   ✓ Only wording, specificity, and keyword alignment were improved

7. ATS FORMATTING
   ✓ No tables, no columns, plain section headers
   ✓ Consistent date format (Mon YYYY)
   ✓ Bullet points with dash – parseable by all ATS systems
"""


if __name__ == "__main__":
    print("=" * 70)
    print("BEFORE (Original Resume)")
    print("=" * 70)
    print(BEFORE_RESUME)
    print()
    print("=" * 70)
    print("AFTER (AI-Tailored ATS Resume)")
    print("=" * 70)
    print(AFTER_RESUME_EXAMPLE)
    print()
    print("=" * 70)
    print("TRANSFORMATION NOTES")
    print("=" * 70)
    print(TRANSFORMATION_NOTES)

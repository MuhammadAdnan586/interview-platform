"""
skills_db.py
-------------
Curated keyword database used to detect skills inside a candidate's CV text.
Why keyword-matching instead of a generic NER model?
  -> Off-the-shelf NER models are trained to find People/Orgs/Locations, not
     tech skills like "scikit-learn" or "Power BI". A maintained skill list +
     fuzzy/substring matching is the same technique real resume-parsing tools
     (e.g. ATS systems) use, and it's 100% free/local — no model download needed.
"""

SKILL_CATEGORIES = {
    "Programming Languages": [
        "python", "java", "c++", "c#", "javascript", "typescript", "r", "sql",
        "go", "golang", "rust", "php", "kotlin", "swift", "matlab", "scala"
    ],
    "Data Science & ML": [
        "machine learning", "deep learning", "data science", "nlp",
        "natural language processing", "computer vision", "scikit-learn",
        "sklearn", "tensorflow", "pytorch", "keras", "pandas", "numpy",
        "matplotlib", "seaborn", "xgboost", "lightgbm", "opencv",
        "hugging face", "transformers", "llm", "large language model",
        "feature engineering", "model deployment", "mlops", "time series",
        "regression", "classification", "clustering", "neural network",
        "random forest", "gradient boosting", "data mining", "statistics"
    ],
    "Web & Backend": [
        "fastapi", "flask", "django", "node.js", "express", "react",
        "next.js", "vue", "angular", "rest api", "graphql", "html", "css"
    ],
    "Databases": [
        "mysql", "postgresql", "mongodb", "redis", "sqlite", "oracle",
        "firebase", "cassandra", "elasticsearch"
    ],
    "Cloud & DevOps": [
        "aws", "azure", "gcp", "google cloud", "docker", "kubernetes",
        "ci/cd", "jenkins", "terraform", "linux", "git", "github", "gitlab"
    ],
    "Tools & Platforms": [
        "power bi", "tableau", "excel", "jupyter", "airflow", "spark",
        "hadoop", "kafka", "streamlit"
    ],
}

# Flattened lookup: skill -> category, all lowercase for matching
ALL_SKILLS = {
    skill: category
    for category, skills in SKILL_CATEGORIES.items()
    for skill in skills
}

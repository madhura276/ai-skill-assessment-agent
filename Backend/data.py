SKILL_CATALOG = {
    "Python": {
        "aliases": ["python", "pandas", "numpy", "flask", "fastapi", "django"],
        "questions": [
            {
                "prompt": "What is the difference between a list and a generator in Python?",
                "keywords": ["memory", "iterator", "lazy", "yield"],
            },
            {
                "prompt": "How would you handle errors and logging in a Python API?",
                "keywords": ["try", "except", "logging", "exception"],
            },
        ],
        "resources": [
            {"title": "Python Official Tutorial", "url": "https://docs.python.org/3/tutorial/"},
            {"title": "Automate the Boring Stuff", "url": "https://automatetheboringstuff.com/"},
        ],
        "adjacent_skills": ["FastAPI", "SQL", "Testing"],
    },
    "SQL": {
        "aliases": ["sql", "postgresql", "mysql", "sqlite", "database"],
        "questions": [
            {
                "prompt": "What is the difference between inner join and left join?",
                "keywords": ["inner join", "left join", "null", "matching"],
            }
        ],
        "resources": [
            {"title": "SQLBolt", "url": "https://sqlbolt.com/"},
        ],
        "adjacent_skills": ["Data Modeling", "ETL"],
    },
}

"""Canonical technical terminology shared by extraction and role matching."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalTerm:
    """A normalized matching key, professional display value, and broad category."""

    key: str
    display: str
    category: str | None
    known: bool


_TERMINAL_TOKEN_PUNCTUATION = re.compile(r"(?<=\w)[.,;:]+$")
_SPACE = re.compile(r"\s+")

# Alias values are semantic matching keys. Display spelling is deliberately kept
# separate so target-role matching never depends on product capitalization.
_ALIASES: dict[str, str] = {
    "ai": "artificial intelligence",
    "artificial intelligence": "artificial intelligence",
    "ml": "machine learning",
    "machine learning": "machine learning",
    "deep learning": "deep learning",
    "generative ai": "generative ai",
    "genai": "generative ai",
    "rag": "retrieval augmented generation",
    "retrieval augmented generation": "retrieval augmented generation",
    "retrieval-augmented generation": "retrieval augmented generation",
    "llm": "large language model",
    "llms": "large language model",
    "large language model": "large language model",
    "large language models": "large language model",
    "ai agent": "ai agents",
    "ai agents": "ai agents",
    "agentic ai": "agentic ai",
    "nlp": "natural language processing",
    "natural language processing": "natural language processing",
    "predictive analytics": "predictive analytics",
    "forecasting": "forecasting",
    "time series": "time series",
    "time-series": "time series",
    "computer vision": "computer vision",
    "image processing": "image processing",
    "cnn": "convolutional neural network",
    "cnns": "convolutional neural network",
    "convolutional neural network": "convolutional neural network",
    "convolutional neural networks": "convolutional neural network",
    "rnn": "recurrent neural network",
    "lstm": "lstm",
    "bilstm": "bilstm",
    "bi-lstm": "bilstm",
    "gan": "generative adversarial network",
    "gans": "generative adversarial network",
    "generative adversarial network": "generative adversarial network",
    "generative adversarial networks": "generative adversarial network",
    "u-net": "u-net",
    "unet": "u-net",
    "patchgan": "patchgan",
    "segresnet": "segresnet",
    "transformer": "transformers",
    "transformers": "transformers",
    "bert": "bert",
    "yolo": "yolo",
    "pix2pix": "pix2pix",
    "pix2pixhd": "pix2pixhd",
    "python": "python",
    "py": "python",
    "java": "java",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "c++": "c++",
    "c#": "c#",
    "pytorch": "pytorch",
    "tensorflow": "tensorflow",
    "opencv": "opencv",
    "monai": "monai",
    "pandas": "pandas",
    "numpy": "numpy",
    "scikit-learn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "spacy": "spacy",
    "sql": "sql",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "mysql": "mysql",
    "mongodb": "mongodb",
    "redis": "redis",
    "clickhouse": "clickhouse",
    "kafka": "kafka",
    "spark": "apache spark",
    "apache spark": "apache spark",
    "airflow": "apache airflow",
    "apache airflow": "apache airflow",
    "etl": "etl",
    "data engineering": "data engineering",
    "database": "database",
    "databases": "database",
    "vector database": "vector database",
    "vector databases": "vector database",
    "docker": "docker",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "aws": "aws",
    "azure": "azure",
    "gcp": "gcp",
    "git": "git",
    "github": "github",
    "github actions": "github actions",
    "ci/cd": "continuous integration",
    "ci cd": "continuous integration",
    "continuous integration": "continuous integration",
    "rest api": "rest api",
    "rest apis": "rest api",
    "restful api": "rest api",
    "restful apis": "rest api",
    "api": "api",
    "apis": "api",
    "openai api": "openai api",
    "fastapi": "fastapi",
    "django": "django",
    "flask": "flask",
    "graphql": "graphql",
    "microservices": "microservices",
    "metabase": "metabase",
    "power bi": "power bi",
    "powerbi": "power bi",
    "tableau": "tableau",
    "excel": "excel",
    "microsoft excel": "excel",
    "ms excel": "excel",
    "firebase": "firebase",
    "flutter": "flutter",
    "react": "react",
    "react.js": "react",
    "reactjs": "react",
    "react native": "react native",
    "node": "node.js",
    "node.js": "node.js",
    "nodejs": "node.js",
    "linux": "linux",
    "terraform": "terraform",
    "jenkins": "jenkins",
    "ansible": "ansible",
    "quickbooks": "quickbooks",
    "sap": "sap",
    "oracle": "oracle",
    "salesforce": "salesforce",
    "jira": "jira",
    "figma": "figma",
    "software testing": "software testing",
    "quality assurance": "quality assurance",
    "ms office": "microsoft office",
    "microsoft office": "microsoft office",
    "office 365": "microsoft office",
    "leadership": "leadership",
    "communication": "communication",
    "planning": "planning",
    "presentation": "presentation",
}

_DISPLAY: dict[str, str] = {
    "artificial intelligence": "Artificial Intelligence",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "generative ai": "Generative AI",
    "retrieval augmented generation": "RAG",
    "large language model": "LLMs",
    "ai agents": "AI Agents",
    "agentic ai": "Agentic AI",
    "natural language processing": "NLP",
    "predictive analytics": "Predictive Analytics",
    "forecasting": "Forecasting",
    "time series": "Time Series",
    "computer vision": "Computer Vision",
    "image processing": "Image Processing",
    "convolutional neural network": "CNN",
    "recurrent neural network": "RNN",
    "lstm": "LSTM",
    "bilstm": "BiLSTM",
    "generative adversarial network": "GANs",
    "u-net": "U-Net",
    "patchgan": "PatchGAN",
    "segresnet": "SegResNet",
    "transformers": "Transformers",
    "bert": "BERT",
    "yolo": "YOLO",
    "pix2pix": "Pix2Pix",
    "pix2pixhd": "Pix2PixHD",
    "python": "Python",
    "java": "Java",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "c++": "C++",
    "c#": "C#",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "opencv": "OpenCV",
    "monai": "MONAI",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "scikit-learn",
    "spacy": "spaCy",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "clickhouse": "ClickHouse",
    "kafka": "Kafka",
    "apache spark": "Apache Spark",
    "apache airflow": "Apache Airflow",
    "etl": "ETL",
    "data engineering": "Data Engineering",
    "database": "Databases",
    "vector database": "Vector Databases",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "git": "Git",
    "github": "GitHub",
    "github actions": "GitHub Actions",
    "continuous integration": "CI/CD",
    "rest api": "REST APIs",
    "api": "APIs",
    "openai api": "OpenAI API",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "graphql": "GraphQL",
    "microservices": "Microservices",
    "metabase": "Metabase",
    "power bi": "Power BI",
    "tableau": "Tableau",
    "excel": "Excel",
    "firebase": "Firebase",
    "flutter": "Flutter",
    "react": "React",
    "react native": "React Native",
    "node.js": "Node.js",
    "linux": "Linux",
    "terraform": "Terraform",
    "jenkins": "Jenkins",
    "ansible": "Ansible",
    "quickbooks": "QuickBooks",
    "sap": "SAP",
    "oracle": "Oracle",
    "salesforce": "Salesforce",
    "jira": "Jira",
    "figma": "Figma",
    "software testing": "Software Testing",
    "quality assurance": "Quality Assurance",
    "microsoft office": "Microsoft Office",
    "leadership": "Leadership",
    "communication": "Communication",
    "planning": "Planning",
    "presentation": "Presentation",
}

_CATEGORIES: dict[str, str] = {
    **{
        key: "ai_ml"
        for key in {
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "generative ai",
            "retrieval augmented generation",
            "large language model",
            "ai agents",
            "agentic ai",
            "natural language processing",
            "predictive analytics",
            "forecasting",
            "time series",
            "computer vision",
            "image processing",
            "convolutional neural network",
            "recurrent neural network",
            "lstm",
            "bilstm",
            "generative adversarial network",
            "u-net",
            "patchgan",
            "segresnet",
            "transformers",
            "bert",
            "yolo",
            "pix2pix",
            "pix2pixhd",
            "pytorch",
            "tensorflow",
            "opencv",
            "monai",
            "scikit-learn",
            "spacy",
        }
    },
    **{
        key: "programming_languages"
        for key in {"python", "java", "javascript", "typescript", "c++", "c#"}
    },
    **{
        key: "data"
        for key in {
            "sql",
            "postgresql",
            "mysql",
            "mongodb",
            "redis",
            "clickhouse",
            "kafka",
            "apache spark",
            "apache airflow",
            "etl",
            "data engineering",
            "database",
            "vector database",
            "pandas",
            "numpy",
        }
    },
    **{
        key: "cloud_devops"
        for key in {
            "docker",
            "kubernetes",
            "aws",
            "azure",
            "gcp",
            "git",
            "github",
            "github actions",
            "continuous integration",
            "linux",
            "terraform",
            "jenkins",
            "ansible",
        }
    },
    **{
        key: "frameworks_tools"
        for key in {
            "rest api",
            "api",
            "openai api",
            "fastapi",
            "django",
            "flask",
            "graphql",
            "microservices",
            "metabase",
            "power bi",
            "tableau",
            "excel",
            "firebase",
            "flutter",
            "react",
            "react native",
            "node.js",
            "software testing",
            "quality assurance",
            "microsoft office",
            "quickbooks",
            "sap",
            "oracle",
            "salesforce",
            "jira",
            "figma",
        }
    },
    **{key: "soft_skills" for key in {"leadership", "communication", "planning", "presentation"}},
}


def clean_technology_token(value: str) -> str:
    """Remove list punctuation while preserving punctuation inside product names."""

    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    text = re.sub(r"^[•●▪◦‣⁃*|,;:\-–—]+\s*", "", text)
    text = _TERMINAL_TOKEN_PUNCTUATION.sub("", text).strip()
    return _SPACE.sub(" ", text)


def normalized_technology_key(value: str) -> str:
    text = clean_technology_token(value).casefold()
    text = text.replace("‑", "-").replace("–", "-").replace("—", "-")
    text = _SPACE.sub(" ", text)
    return _ALIASES.get(text, text)


def canonical_technology(value: str) -> CanonicalTerm:
    """Return a known display spelling or preserve an unknown token conservatively."""

    cleaned = clean_technology_token(value)
    key = normalized_technology_key(cleaned)
    known = key in _DISPLAY
    return CanonicalTerm(
        key=key,
        display=_DISPLAY.get(key, cleaned),
        category=_CATEGORIES.get(key),
        known=known,
    )


def is_known_technology(value: str) -> bool:
    return canonical_technology(value).known


def terminology_aliases() -> dict[str, str]:
    """Expose a copy for deterministic target-role alias resolution."""

    return dict(_ALIASES)

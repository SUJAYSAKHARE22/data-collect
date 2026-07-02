"""
Main entry point to run the FastAPI application.

Can be run from the project root directory:
    python run.py
    uvicorn run:app --reload
"""
import sys
from pathlib import Path

# Ensure the project root is in the path so imports work correctly
_root_dir = str(Path(__file__).resolve().parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

import uvicorn
from app.main import app  # Expose app for 'uvicorn run:app --reload'

if __name__ == "__main__":
    uvicorn.run("run:app", host="127.0.0.1", port=8000, reload=True)

import os
import sys
import uvicorn

if __name__ == "__main__":
    print("=" * 70)
    print("  HistoLens AI - Enterprise Digital Pathology & WSI AI System")
    print("  AIRA Matrix Trainee Engineer Portfolio Project")
    print("=" * 70)
    print("Starting local server on http://127.0.0.1:8000 ...")
    print("Open your browser and navigate to: http://127.0.0.1:8000")
    print("Press Ctrl+C to stop.")
    print("=" * 70)
    
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False, log_level="info")

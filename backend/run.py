import os
import uvicorn
from mira.api.main import app  # <-- Directly import the FastAPI app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

"""
Looma backend entry point.
Usage: python run.py
"""
import os
from src.app import create_app

app = create_app(os.getenv("FLASK_ENV", "development"))

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5200))
    app.run(host="0.0.0.0", port=port, debug=True)

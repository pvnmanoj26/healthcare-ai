import os
from config.settings import DEBUG

def main():
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Flask App on port {port}...")
    from app.main import app
    app.run(host="0.0.0.0", port=port, debug=DEBUG)

if __name__ == "__main__":
    main()

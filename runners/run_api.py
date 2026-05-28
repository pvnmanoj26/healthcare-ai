import os
import uvicorn

def main():
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting FastAPI server on port {port}...")
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    main()

import uvicorn

if __name__ == "__main__":
    # This specifically tells Uvicorn to only watch the 'app' folder
    # and ignore everything else (like .venv, logs, or data)
    uvicorn.run("app.api:app", host="127.0.0.1", port=18081, reload=True, reload_dirs=["./app"])
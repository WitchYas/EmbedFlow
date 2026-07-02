import os
import subprocess
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path

router = APIRouter()

MANIFEST_PATH = Path("firmware/manifest.yml")

class FirmwarePublishRequest(BaseModel):
    version: str
    image: str = "ubuntu:22.04"
    device_profile: str = "rpi4"
    description: str = ""
    auto_push: bool = True

def run_git_command(command: list):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e.stderr}")
        raise HTTPException(status_code=500, detail=f"Git operation failed: {e.stderr}")

@router.post("/publish")
async def publish_firmware(req: FirmwarePublishRequest):
    """
    Automates the 'pushing' of firmware.
    1. Updates manifest.yml
    2. Commits and Pushes to GitHub (if auto_push is True)
    """
    if not MANIFEST_PATH.parent.exists():
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 1. Update manifest.yml
    manifest = {
        "version": req.version,
        "image": req.image,
        "device_profile": req.device_profile,
        "description": req.description
    }
    
    with open(MANIFEST_PATH, "w") as f:
        yaml.dump(manifest, f)

    # 2. Automated Git Push
    if req.auto_push:
        try:
            # Check if it's a git repo
            run_git_command(["git", "rev-parse", "--is-inside-work-tree"])
            
            # Add, Commit, Push
            run_git_command(["git", "add", str(MANIFEST_PATH)])
            
            # Simple message
            commit_msg = f"chore(firmware): auto-publish {req.version}"
            run_git_command(["git", "commit", "-m", commit_msg])
            
            # Push (requires GITHUB_TOKEN or SSH setup in the environment)
            # Note: In a real CI environment, we'd use the token.
            # Here we assume the user has git push configured or we use the remote URL with token if provided.
            run_git_command(["git", "push"])
            
            return {"status": "success", "message": f"Published and pushed version {req.version}"}
        except Exception as e:
            return {
                "status": "partial_success", 
                "message": f"Manifest updated to {req.version}, but git push failed. Check your local git config.",
                "error": str(e)
            }

    return {"status": "success", "message": f"Manifest updated locally to {req.version}"}

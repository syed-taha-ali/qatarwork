"""
Secure document handling service for sensitive user files (QID, credentials)
"""
from pathlib import Path
from typing import Optional, List
from fastapi import UploadFile, HTTPException
import os
import uuid


# Private documents directory (NOT web-accessible)
PRIVATE_DOCS_DIR = Path("app/private/documents")
PRIVATE_DOCS_DIR.mkdir(parents=True, exist_ok=True)

# Allowed file types
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.pdf'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# File type labels
QID_FRONT = "qid_front"
QID_BACK = "qid_back"
CREDENTIAL_PREFIX = "credential"


def get_user_docs_directory(user_id: int) -> Path:
    """Get or create user's private documents directory."""
    user_dir = PRIVATE_DOCS_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def validate_file(file: UploadFile) -> None:
    """Validate uploaded file type and size."""
    if not file or not file.filename:
        raise HTTPException(400, "No file provided")
    
    # Check file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400, 
            f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Max size: 10MB")


async def save_qid_document(
    user_id: int, 
    file: UploadFile, 
    side: str  # "front" or "back"
) -> str:
    """
    Save QID document securely.
    Returns the filename saved.
    """
    validate_file(file)
    
    # Get user directory
    user_dir = get_user_docs_directory(user_id)
    
    # Generate filename
    ext = Path(file.filename).suffix.lower()
    filename = f"qid_{side}{ext}"
    filepath = user_dir / filename
    
    # Delete old file if exists
    if filepath.exists():
        filepath.unlink()
    
    # Save new file
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    
    return filename


async def save_credential_document(
    user_id: int,
    file: UploadFile,
    index: int  # 1-5
) -> str:
    """
    Save credential document securely.
    Returns the filename saved.
    """
    validate_file(file)
    
    if index < 1 or index > 5:
        raise HTTPException(400, "Credential index must be between 1 and 5")
    
    # Get user directory
    user_dir = get_user_docs_directory(user_id)
    
    # Generate filename
    ext = Path(file.filename).suffix.lower()
    filename = f"credential_{index}{ext}"
    filepath = user_dir / filename
    
    # Delete old file if exists
    if filepath.exists():
        filepath.unlink()
    
    # Save new file
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    
    return filename


def get_user_documents(user_id: int) -> dict:
    """
    Get list of documents for a user.
    Returns dict with qid_front, qid_back, credentials list.
    """
    user_dir = get_user_docs_directory(user_id)
    
    result = {
        "qid_front": None,
        "qid_back": None,
        "credentials": []
    }
    
    # Check for QID documents
    for ext in ALLOWED_EXTENSIONS:
        qid_front = user_dir / f"qid_front{ext}"
        if qid_front.exists():
            result["qid_front"] = qid_front.name
            
        qid_back = user_dir / f"qid_back{ext}"
        if qid_back.exists():
            result["qid_back"] = qid_back.name
    
    # Check for credentials
    for i in range(1, 6):
        for ext in ALLOWED_EXTENSIONS:
            cred_file = user_dir / f"credential_{i}{ext}"
            if cred_file.exists():
                result["credentials"].append({
                    "index": i,
                    "filename": cred_file.name
                })
                break
    
    return result


def delete_document(user_id: int, filename: str) -> bool:
    """
    Delete a specific document for a user.
    Returns True if deleted, False if not found.
    """
    user_dir = get_user_docs_directory(user_id)
    filepath = user_dir / filename
    
    if filepath.exists() and filepath.parent == user_dir:  # Security check
        filepath.unlink()
        return True
    
    return False


def delete_all_user_documents(user_id: int) -> int:
    """
    Delete all documents for a user.
    Returns count of files deleted.
    """
    user_dir = get_user_docs_directory(user_id)
    
    count = 0
    for filepath in user_dir.iterdir():
        if filepath.is_file():
            filepath.unlink()
            count += 1
    
    # Remove directory if empty
    try:
        user_dir.rmdir()
    except:
        pass
    
    return count


def get_document_path(user_id: int, filename: str) -> Optional[Path]:
    """
    Get full path to a document.
    Returns None if file doesn't exist or security check fails.
    """
    user_dir = get_user_docs_directory(user_id)
    filepath = user_dir / filename
    
    # Security check: ensure file is within user's directory
    if not filepath.resolve().is_relative_to(user_dir.resolve()):
        return None
    
    if filepath.exists() and filepath.is_file():
        return filepath
    
    return None

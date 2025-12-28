"""
Document handler for uploading and managing documents with Gemini
"""

from typing import List, Optional
from pathlib import Path
import google.generativeai as genai


class DocumentHandler:
    """Handles document uploads and integration with Gemini"""

    def __init__(self):
        self.uploaded_files = []

    def upload_document(self, file_path: str) -> Optional[any]:
        """
        Upload a document to Gemini

        Args:
            file_path: Path to the document file

        Returns:
            Uploaded file object or None if failed
        """
        try:
            uploaded_file = genai.upload_file(file_path)
            self.uploaded_files.append(uploaded_file)
            return uploaded_file
        except Exception as e:
            print(f"Error uploading {file_path}: {e}")
            return None

    def get_uploaded_files(self) -> List:
        """Get list of uploaded file objects"""
        return self.uploaded_files

    def clear(self):
        """Clear uploaded files"""
        self.uploaded_files.clear()

    def create_document_context(self, task: str) -> str:
        """
        Create enhanced task description with document context

        Args:
            task: Original task description

        Returns:
            Enhanced task with document context
        """
        if not self.uploaded_files:
            return task

        doc_names = [Path(f.display_name).name for f in self.uploaded_files]
        doc_list = "\n".join([f"- {name}" for name in doc_names])

        enhanced_task = f"""{task}

IMPORTANT CONTEXT:
The following documents have been uploaded and are available for use:
{doc_list}

Please use the information from these documents when:
- Filling out forms
- Answering questions
- Providing personal information
- Extracting data

Extract relevant information from the documents and use it appropriately for the task.
"""
        return enhanced_task

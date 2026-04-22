"""
Claude API tool definitions.
Each entry maps directly to an Anthropic tools= parameter dict.
"""
from __future__ import annotations

CLASSIFY_EMAIL_TOOL = {
    "name": "classify_email",
    "description": (
        "Classify an email into one of: invoice, important, spam, other. "
        "Returns category, confidence score (0-1), and a short reason."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "Email subject line"},
            "sender":  {"type": "string", "description": "Sender email address"},
            "body":    {"type": "string", "description": "Email body text (max 1000 chars)"},
        },
        "required": ["subject", "sender", "body"],
    },
}

DOWNLOAD_ATTACHMENT_TOOL = {
    "name": "download_attachment",
    "description": (
        "Download and decode a base64-encoded email attachment. "
        "Returns the filename and byte size."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename":     {"type": "string", "description": "Original filename"},
            "content_b64":  {"type": "string", "description": "Base64-encoded file content"},
            "content_type": {"type": "string", "description": "MIME type of the attachment"},
        },
        "required": ["filename", "content_b64"],
    },
}

SAVE_TO_EXCEL_TOOL = {
    "name": "save_to_excel",
    "description": (
        "Append an email processing record to the Excel report. "
        "Skips duplicates. Returns whether the row was written."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "date":            {"type": "string", "description": "Email date (YYYY-MM-DD HH:MM:SS)"},
            "sender":          {"type": "string", "description": "Sender email"},
            "subject":         {"type": "string", "description": "Email subject"},
            "category":        {"type": "string", "enum": ["invoice", "important", "spam", "other"]},
            "confidence":      {"type": "number", "description": "Classification confidence 0-1"},
            "file_path":       {"type": "string", "description": "Saved attachment path(s)"},
            "has_attachments": {"type": "boolean", "description": "Whether email had attachments"},
        },
        "required": ["date", "sender", "subject", "category", "confidence", "has_attachments"],
    },
}

MOVE_FILE_TOOL = {
    "name": "move_file",
    "description": (
        "Save an attachment binary to the correct categorized storage folder. "
        "Handles duplicate detection and filename collisions automatically."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename":    {"type": "string", "description": "Filename to save"},
            "content_b64": {"type": "string", "description": "Base64-encoded file content"},
            "category":    {"type": "string", "enum": ["invoice", "important", "spam", "other"]},
            "sender":      {"type": "string", "description": "Sender email (for metadata)"},
        },
        "required": ["filename", "content_b64", "category"],
    },
}

ALL_TOOLS = [CLASSIFY_EMAIL_TOOL, DOWNLOAD_ATTACHMENT_TOOL, SAVE_TO_EXCEL_TOOL, MOVE_FILE_TOOL]

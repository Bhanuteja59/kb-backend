from __future__ import annotations
import httpx

DRIVE_FILES = "https://www.googleapis.com/drive/v3/files/{file_id}"
DRIVE_MEDIA = "https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

async def download_drive_file(file_id: str, access_token: str) -> tuple[str, bytes]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=60) as client:
        # metadata
        meta = await client.get(DRIVE_FILES.format(file_id=file_id), headers=headers, params={"fields": "name,mimeType,size"})
        meta.raise_for_status()
        m = meta.json()
        name = m.get("name") or f"{file_id}"
        mime_type = m.get("mimeType")

        # Handle Google Docs/Sheets/Slides (must be exported)
        # We'll export everything to PDF for simplicity, as we have a PDF extractor
        export_mime = None
        if mime_type == "application/vnd.google-apps.document":
            export_mime = "application/pdf"
            name += ".pdf"
        elif mime_type == "application/vnd.google-apps.spreadsheet":
            export_mime = "application/pdf"
            name += ".pdf"
        elif mime_type == "application/vnd.google-apps.presentation":
            export_mime = "application/pdf"
            name += ".pdf"

        if export_mime:
            # Export
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
            content = await client.get(url, headers=headers, params={"mimeType": export_mime})
        else:
            # Binary download
            content = await client.get(DRIVE_MEDIA.format(file_id=file_id), headers=headers)
        
        content.raise_for_status()
        return name, content.content

"""
Google Docs MCP Tools

This module provides MCP tools for interacting with Google Docs API and managing Google Docs via Drive.
"""
import logging
import asyncio
import io
from typing import List

from mcp import types
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# Auth & server utilities
from auth.service_decorator import require_google_service, require_multiple_services
from core.utils import extract_office_xml_text, handle_http_errors
from core.server import server

logger = logging.getLogger(__name__)

@server.tool()
@require_google_service("drive", "drive_read")
@handle_http_errors("search_docs")
async def search_docs(
    service,
    user_google_email: str,
    query: str,
    page_size: int = 10,
) -> str:
    """
    Searches for Google Docs by name using Drive API (mimeType filter).

    Args:
        query (str): Search query to match against document names.
        page_size (int): Maximum number of documents to return. Defaults to 10.

    Returns:
        str: A formatted list of Google Docs matching the search query.
    """
    logger.info(f"[search_docs] Email={user_google_email}, Query='{query}'")

    escaped_query = query.replace("'", "\\'")

    response = await asyncio.to_thread(
        service.files().list(
            q=f"name contains '{escaped_query}' and mimeType='application/vnd.google-apps.document' and trashed=false",
            pageSize=page_size,
            fields="files(id, name, createdTime, modifiedTime, webViewLink)"
        ).execute
    )
    files = response.get('files', [])
    if not files:
        return f"No Google Docs found matching '{query}'."

    output = [f"Found {len(files)} Google Docs matching '{query}':"]
    for f in files:
        output.append(
            f"- {f['name']} (ID: {f['id']}) Modified: {f.get('modifiedTime')} Link: {f.get('webViewLink')}"
        )
    return "\n".join(output)

@server.tool()
@require_multiple_services([
    {"service_type": "drive", "scopes": "drive_read", "param_name": "drive_service"},
    {"service_type": "docs", "scopes": "docs_read", "param_name": "docs_service"}
])
@handle_http_errors("get_doc_content")
async def get_doc_content(
    drive_service,
    docs_service,
    user_google_email: str,
    document_id: str,
) -> str:
    """
    Retrieves content of a Google Doc or a Drive file (like .docx) identified by document_id.
    - Native Google Docs: Fetches content via Docs API.
    - Office files (.docx, etc.) stored in Drive: Downloads via Drive API and extracts text.

    Args:
        document_id (str): The ID of the document or file to retrieve content from.

    Returns:
        str: The document content with metadata header.
    """
    logger.info(f"[get_doc_content] Invoked. Document/File ID: '{document_id}' for user '{user_google_email}'")

    # Step 2: Get file metadata from Drive
    file_metadata = await asyncio.to_thread(
        drive_service.files().get(
            fileId=document_id, fields="id, name, mimeType, webViewLink"
        ).execute
    )
    mime_type = file_metadata.get("mimeType", "")
    file_name = file_metadata.get("name", "Unknown File")
    web_view_link = file_metadata.get("webViewLink", "#")

    logger.info(f"[get_doc_content] File '{file_name}' (ID: {document_id}) has mimeType: '{mime_type}'")

    body_text = "" # Initialize body_text

    # Step 3: Process based on mimeType
    if mime_type == "application/vnd.google-apps.document":
        logger.info(f"[get_doc_content] Processing as native Google Doc.")
        doc_data = await asyncio.to_thread(
            docs_service.documents().get(documentId=document_id).execute
        )
        body_elements = doc_data.get('body', {}).get('content', [])

        processed_text_lines: List[str] = []
        for element in body_elements:
            if 'paragraph' in element:
                paragraph = element.get('paragraph', {})
                para_elements = paragraph.get('elements', [])
                current_line_text = ""
                for pe in para_elements:
                    text_run = pe.get('textRun', {})
                    if text_run and 'content' in text_run:
                        current_line_text += text_run['content']
                if current_line_text.strip():
                        processed_text_lines.append(current_line_text)
        body_text = "".join(processed_text_lines)
    else:
        logger.info(f"[get_doc_content] Processing as Drive file (e.g., .docx, other). MimeType: {mime_type}")

        export_mime_type_map = {
                # Example: "application/vnd.google-apps.spreadsheet"z: "text/csv",
                # Native GSuite types that are not Docs would go here if this function
                # was intended to export them. For .docx, direct download is used.
        }
        effective_export_mime = export_mime_type_map.get(mime_type)

        request_obj = (
            drive_service.files().export_media(fileId=document_id, mimeType=effective_export_mime)
            if effective_export_mime
            else drive_service.files().get_media(fileId=document_id)
        )

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request_obj)
        loop = asyncio.get_event_loop()
        done = False
        while not done:
            status, done = await loop.run_in_executor(None, downloader.next_chunk)

        file_content_bytes = fh.getvalue()

        office_text = extract_office_xml_text(file_content_bytes, mime_type)
        if office_text:
            body_text = office_text
        else:
            try:
                body_text = file_content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                body_text = (
                    f"[Binary or unsupported text encoding for mimeType '{mime_type}' - "
                    f"{len(file_content_bytes)} bytes]"
                )

    header = (
        f'File: "{file_name}" (ID: {document_id}, Type: {mime_type})\n'
        f'Link: {web_view_link}\n\n--- CONTENT ---\n'
    )
    return header + body_text

@server.tool()
@require_google_service("drive", "drive_read")
@handle_http_errors("list_docs_in_folder")
async def list_docs_in_folder(
    service,
    user_google_email: str,
    folder_id: str = 'root',
    page_size: int = 100
) -> str:
    """
    Lists Google Docs within a specific Drive folder.

    Args:
        folder_id (str): The ID of the folder to search in. Defaults to 'root'.
        page_size (int): Maximum number of documents to return. Defaults to 100.

    Returns:
        str: A formatted list of Google Docs in the specified folder.
    """
    logger.info(f"[list_docs_in_folder] Invoked. Email: '{user_google_email}', Folder ID: '{folder_id}'")

    rsp = await asyncio.to_thread(
        service.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false",
            pageSize=page_size,
            fields="files(id, name, modifiedTime, webViewLink)"
        ).execute
    )
    items = rsp.get('files', [])
    if not items:
        return f"No Google Docs found in folder '{folder_id}'."
    out = [f"Found {len(items)} Docs in folder '{folder_id}':"]
    for f in items:
        out.append(f"- {f['name']} (ID: {f['id']}) Modified: {f.get('modifiedTime')} Link: {f.get('webViewLink')}")
    return "\n".join(out)

@server.tool()
@require_google_service("docs", "docs_write")
@handle_http_errors("create_doc")
async def create_doc(
    service,
    user_google_email: str,
    title: str,
    content: str = '',
) -> str:
    """
    Creates a new Google Doc and optionally inserts initial content.

    Args:
        title (str): The title of the new document.
        content (str): Optional initial content to insert into the document. Defaults to empty string.

    Returns:
        str: Confirmation message with document ID and link.
    """
    logger.info(f"[create_doc] Invoked. Email: '{user_google_email}', Title='{title}'")

    doc = await asyncio.to_thread(service.documents().create(body={'title': title}).execute)
    doc_id = doc.get('documentId')
    if content:
        requests = [{'insertText': {'location': {'index': 1}, 'text': content}}]
        await asyncio.to_thread(service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute)
    link = f"https://docs.google.com/document/d/{doc_id}/edit"
    msg = f"Created Google Doc '{title}' (ID: {doc_id}) for {user_google_email}. Link: {link}"
    logger.info(f"Successfully created Google Doc '{title}' (ID: {doc_id}) for {user_google_email}. Link: {link}")
    return msg


@server.tool()
@require_google_service("drive", "drive_read")
@handle_http_errors("read_doc_comments")
async def read_doc_comments(
    service,
    user_google_email: str,
    document_id: str,
) -> str:
    """
    Read all comments from a Google Doc.

    Args:
        document_id (str): The ID of the Google Document.

    Returns:
        str: A formatted list of all comments and replies in the document.
    """
    logger.info(f"[read_doc_comments] Reading comments for document {document_id}")

    response = await asyncio.to_thread(
        service.comments().list(
            fileId=document_id,
            fields="comments(id,content,author,createdTime,modifiedTime,resolved,replies(content,author,id,createdTime,modifiedTime))"
        ).execute
    )
    
    comments = response.get('comments', [])
    
    if not comments:
        return f"No comments found in document {document_id}"
    
    output = [f"Found {len(comments)} comments in document {document_id}:\n"]
    
    for comment in comments:
        author = comment.get('author', {}).get('displayName', 'Unknown')
        content = comment.get('content', '')
        created = comment.get('createdTime', '')
        resolved = comment.get('resolved', False)
        comment_id = comment.get('id', '')
        status = " [RESOLVED]" if resolved else ""
        
        output.append(f"Comment ID: {comment_id}")
        output.append(f"Author: {author}")
        output.append(f"Created: {created}{status}")
        output.append(f"Content: {content}")
        
        # Add replies if any
        replies = comment.get('replies', [])
        if replies:
            output.append(f"  Replies ({len(replies)}):")
            for reply in replies:
                reply_author = reply.get('author', {}).get('displayName', 'Unknown')
                reply_content = reply.get('content', '')
                reply_created = reply.get('createdTime', '')
                reply_id = reply.get('id', '')
                output.append(f"    Reply ID: {reply_id}")
                output.append(f"    Author: {reply_author}")
                output.append(f"    Created: {reply_created}")
                output.append(f"    Content: {reply_content}")
        
        output.append("")  # Empty line between comments
    
    return "\n".join(output)


@server.tool()
@require_google_service("drive", "drive_file")
@handle_http_errors("reply_to_comment")
async def reply_to_comment(
    service,
    user_google_email: str,
    document_id: str,
    comment_id: str,
    reply_content: str,
) -> str:
    """
    Reply to a specific comment in a Google Doc.

    Args:
        document_id (str): The ID of the Google Document.
        comment_id (str): The ID of the comment to reply to.
        reply_content (str): The content of the reply.

    Returns:
        str: Confirmation message with reply details.
    """
    logger.info(f"[reply_to_comment] Replying to comment {comment_id} in document {document_id}")

    body = {'content': reply_content}
    
    reply = await asyncio.to_thread(
        service.replies().create(
            fileId=document_id,
            commentId=comment_id,
            body=body,
            fields="id,content,author,createdTime,modifiedTime"
        ).execute
    )
    
    reply_id = reply.get('id', '')
    author = reply.get('author', {}).get('displayName', 'Unknown')
    created = reply.get('createdTime', '')
    
    return f"Reply posted successfully!\nReply ID: {reply_id}\nAuthor: {author}\nCreated: {created}\nContent: {reply_content}"


@server.tool()
@require_google_service("drive", "drive_file")
@handle_http_errors("create_doc_comment")
async def create_doc_comment(
    service,
    user_google_email: str,
    document_id: str,
    comment_content: str,
) -> str:
    """
    Create a new comment on a Google Doc.

    Args:
        document_id (str): The ID of the Google Document.
        comment_content (str): The content of the comment.

    Returns:
        str: Confirmation message with comment details.
    """
    logger.info(f"[create_doc_comment] Creating comment in document {document_id}")

    body = {"content": comment_content}
    
    comment = await asyncio.to_thread(
        service.comments().create(
            fileId=document_id,
            body=body,
            fields="id,content,author,createdTime,modifiedTime"
        ).execute
    )
    
    comment_id = comment.get('id', '')
    author = comment.get('author', {}).get('displayName', 'Unknown')
    created = comment.get('createdTime', '')
    
    return f"Comment created successfully!\nComment ID: {comment_id}\nAuthor: {author}\nCreated: {created}\nContent: {comment_content}"


@server.tool()
@require_google_service("drive", "drive_file")
@handle_http_errors("resolve_comment")
async def resolve_comment(
    service,
    user_google_email: str,
    document_id: str,
    comment_id: str,
) -> str:
    """
    Resolve a comment in a Google Doc.

    Args:
        document_id (str): The ID of the Google Document.
        comment_id (str): The ID of the comment to resolve.

    Returns:
        str: Confirmation message.
    """
    logger.info(f"[resolve_comment] Resolving comment {comment_id} in document {document_id}")

    body = {"resolved": True}
    
    await asyncio.to_thread(
        service.comments().update(
            fileId=document_id,
            commentId=comment_id,
            body=body
        ).execute
    )
    
    return f"Comment {comment_id} has been resolved successfully."

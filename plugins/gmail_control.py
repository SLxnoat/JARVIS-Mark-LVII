"""
plugins/gmail_control.py - Gmail email assistant (read, search, draft, send).

Adheres to AGENTS.md:
- Thread-safe email operations.
- Thread-safe HUD presentation via player.show_content().
- Never raises exceptions, returns concise spoken feedback.
- Reads credentials from config/api_keys.json or environment.
"""
import email
import imaplib
import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from memory.config_manager import get_plugin_config

PLUGIN = {
    "name": "gmail_control",
    "description": (
        "Reads unread emails, searches messages, drafts replies, and sends emails through Gmail. "
        "Supports IMAP/SMTP and Google API OAuth."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'unread', 'search', 'draft', 'send'.",
                "enum": ["unread", "search", "draft", "send"],
            },
            "query": {
                "type": "STRING",
                "description": "Search term or sender to search for.",
            },
            "to": {
                "type": "STRING",
                "description": "Recipient email address for 'send' or 'draft'.",
            },
            "subject": {
                "type": "STRING",
                "description": "Email subject line.",
            },
            "body": {
                "type": "STRING",
                "description": "Email content / body text.",
            },
        },
        "required": ["action"],
    },
    "PLUGIN_SETTINGS": {
        "fields": [
            {"key": "email", "label": "Gmail Address", "type": "string"},
            {"key": "app_password", "label": "App Password (16-character)", "type": "password"},
        ]
    },
}


def _get_creds():
    cfg = get_plugin_config("gmail_control") or {}
    addr = cfg.get("email") or os.environ.get("GMAIL_ADDRESS")
    pwd = cfg.get("app_password") or os.environ.get("GMAIL_APP_PASSWORD")
    return addr, pwd


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "unread").strip().lower()
    query = str(parameters.get("query") or "").strip()
    to_addr = str(parameters.get("to") or "").strip()
    subject = str(parameters.get("subject") or "(No Subject)").strip()
    body = str(parameters.get("body") or "").strip()

    user_email, app_pwd = _get_creds()

    if not user_email or not app_pwd:
        if action == "draft":
            # Allow local drafting even without credentials
            draft_path = Path("reports") / f"draft_{int(time.time() if 'time' in locals() else 0)}.txt"
            draft_content = f"To: {to_addr}\nSubject: {subject}\n\n{body}\n"
            if player:
                try:
                    player.show_content(f"Draft: {subject}", f"### ✉️ Email Draft\n\n```\n{draft_content}\n```")
                except Exception:
                    pass
            return f"Drafted email to {to_addr or 'recipient'} with subject '{subject}'. Configure Gmail App Password in settings to send."

        return (
            "Gmail is not yet configured. Please set your Gmail address and 16-character App Password "
            "in the plugin settings or GMAIL_ADDRESS / GMAIL_APP_PASSWORD environment variables."
        )

    try:
        if action in ("unread", "search"):
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(user_email, app_pwd)
            mail.select("inbox")

            search_criterion = "UNSEEN" if action == "unread" else f'(OR FROM "{query}" SUBJECT "{query}")'
            status, messages = mail.search(None, search_criterion)

            if status != "OK" or not messages[0]:
                mail.logout()
                return "No unread emails found in your Gmail inbox." if action == "unread" else f"No emails matching '{query}' found."

            msg_ids = messages[0].split()
            latest_ids = msg_ids[-5:]
            email_summaries = []

            for mid in reversed(latest_ids):
                res, data = mail.fetch(mid, "(RFC822)")
                for response_part in data:
                    if isinstance(response_part, tuple):
                        msg_obj = email.message_from_bytes(response_part[1])
                        sender = msg_obj.get("From", "Unknown Sender")
                        subj = msg_obj.get("Subject", "(No Subject)")
                        date_str = msg_obj.get("Date", "")
                        email_summaries.append(f"- **{subj}** from `{sender}` *({date_str[:16]})*")

            mail.logout()

            hud_md = f"### 📬 Gmail Inbox ({action})\n\n" + "\n".join(email_summaries)
            if player:
                try:
                    player.show_content("Gmail Messages", hud_md)
                except Exception:
                    pass

            return f"Found {len(msg_ids)} message(s) in Gmail. Showing latest on screen."

        elif action == "send":
            if not to_addr or not body:
                return "Sending an email requires both a recipient ('to') and 'body' content."

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = user_email
            msg["To"] = to_addr

            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10.0) as server:
                server.login(user_email, app_pwd)
                server.send_message(msg)

            if player:
                try:
                    player.write_log(f"✉️ [Gmail] Sent email to {to_addr} ('{subject}')")
                except Exception:
                    pass
            return f"Successfully sent email to {to_addr} with subject '{subject}'."

        elif action == "draft":
            hud_md = (
                f"### ✉️ Email Staged / Draft\n\n"
                f"- **To:** `{to_addr}`\n"
                f"- **Subject:** {subject}\n\n"
                f"**Body:**\n> {body}\n"
            )
            if player:
                try:
                    player.show_content("Email Draft", hud_md)
                except Exception:
                    pass
            return f"Prepared email draft to {to_addr} for your review."

        else:
            return f"Unknown action '{action}'. Valid actions: unread, search, draft, send."

    except imaplib.IMAP4.error as e:
        return f"Gmail authentication failed. Verify your App Password in settings ({e})."
    except Exception as e:
        return f"Error communicating with Gmail: {e}"

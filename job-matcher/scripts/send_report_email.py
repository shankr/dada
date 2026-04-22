#!/usr/bin/env python3

import os
import smtplib
import sys
from email.message import EmailMessage


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/send_report_email.py <report_path>", file=sys.stderr)
        return 1

    report_path = sys.argv[1]
    email_to = os.environ.get("JOB_MATCHER_EMAIL_TO", "").strip()
    email_from = os.environ.get("JOB_MATCHER_EMAIL_FROM", "").strip()
    smtp_username = os.environ.get("JOB_MATCHER_SMTP_USERNAME", "").strip()
    smtp_password = os.environ.get("JOB_MATCHER_SMTP_PASSWORD", "").strip()
    subject = os.environ.get("JOB_MATCHER_EMAIL_SUBJECT", "Job Matcher Report").strip()

    missing = [
        name
        for name, value in [
            ("JOB_MATCHER_EMAIL_TO", email_to),
            ("JOB_MATCHER_EMAIL_FROM", email_from),
            ("JOB_MATCHER_SMTP_USERNAME", smtp_username),
            ("JOB_MATCHER_SMTP_PASSWORD", smtp_password),
        ]
        if not value
    ]
    if missing:
        print(f"Missing required email env vars: {', '.join(missing)}", file=sys.stderr)
        return 1

    with open(report_path, "r", encoding="utf-8") as fh:
        report_text = fh.read()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.set_content(report_text)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(msg)

    print(f"Email sent to {email_to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Postmark CMS - Email-Powered Content Management

![Postmark CMS Screenshot](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/5qkg24afkdm6ducr2xcs.jpg)

## 📌 Introduction
Postmark CMS is a lightweight content management system that transforms emails into website posts using Postmark's inbound webhooks. Designed for creators, teams, and anyone who prefers email workflows, it eliminates complex dashboards while providing full content control through simple email commands.

## Key Features
- **Email-First Publishing**: Create posts by sending emails
- **Command-Based Editing**: Update content with email subject lines
- **Image Handling**: Attachments automatically become post media
- **Admin Dashboard**: Manage all content with a simple interface

## 🛠️ Tech Stack
| Component       | Technology |
|-----------------|------------|
| Backend         | Python + Flask |
| Database        | SQLite |
| Frontend        | Jinja2 Templates |
| Email Processing| Postmark Inbound Webhooks |

## 🚀 Local Installation

### Prerequisites
- Python 3.8+
- Postmark account with inbound webhook setup
- SQLite (comes with Python)

### Setup Steps
```bash
# 1. Clone repository
git clone https://github.com/amplitud3/post-mark-cms.git
cd post-mark-cms

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your:
# - Postmark inbound webhook details
# - ALLOWED_SENDERS (authorized email addresses)
# - ADMIN credentials

# 5. Initialize database
python init_db.py

# 6. Run application
python server.py



TO CREATE POST
To: your-inbound@postmark.address
Subject: Your Post Title
Body: Your content here
[Attachments: Optional images]


TO EDIT POST
To: your-inbound@postmark.address
Subject: EDIT #1234
Body: New updated content

TO DELETE POST
To: your-inbound@postmark.address
Subject: DELETE #5678
[Body can be empty]


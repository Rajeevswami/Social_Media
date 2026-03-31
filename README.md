# 🔗 Connectify — Instagram-Style Social Media Platform

<div align="center">

![Connectify](https://img.shields.io/badge/Connectify-Social%20Platform-0095f6?style=for-the-badge&logo=instagram&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.0.1-092E20?style=for-the-badge&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**A full-featured Instagram-inspired social media platform built with Django**

[🌐 Live Demo](#) • [📸 Screenshots](#-screenshots) • [⚡ Features](#-features) • [🚀 Installation](#-installation)

</div>

---

## 📖 About

**Connectify** is a modern, full-stack social media platform inspired by Instagram, built using **Django 6.0.1** and **Python 3.14**. It features a stunning dark-mode UI with a pure black aesthetic, real-time interactions, stories, reels, direct messaging, and all the core features you'd expect from a professional social media application.

> Built as a portfolio project to demonstrate full-stack web development skills with Django.

---

## ✨ Features

### 📱 Core Social Features
| Feature | Status |
|---------|--------|
| User Registration & Login | ✅ Done |
| Instagram-Style Dark UI | ✅ Done |
| Post Photos & Videos (Reels) | ✅ Done |
| Multi-Image Carousel Posts | ✅ Done |
| Like & Unlike Posts | ✅ Done |
| Comment on Posts | ✅ Done |
| Reply to Comments (Threaded) | ✅ Done |
| Like Individual Comments | ✅ Done |
| Save / Bookmark Posts | ✅ Done |
| Share Posts (Copy Link) | ✅ Done |
| Edit & Archive Posts | ✅ Done |
| Hashtag Support (#tag) | ✅ Done |
| @Mention Users | ✅ Done |
| Location Tags on Posts | ✅ Done |
| Photo Filters (B&W, Sepia, etc.) | ✅ Done |
| Double-Tap to Like (Mobile) | ✅ Done |

### 👤 Profile System
| Feature | Status |
|---------|--------|
| User Profiles with Avatar | ✅ Done |
| Followers / Following System | ✅ Done |
| Verified Badge (✓ Blue Check) | ✅ Done |
| Private Account Mode | ✅ Done |
| Story Highlights on Profile | ✅ Done |
| Edit Profile | ✅ Done |
| Followers & Following Lists | ✅ Done |
| Mutual Followers Display | ✅ Done |
| Block / Unblock Users | ✅ Done |
| Close Friends List | ✅ Done |
| Saved Posts Collection | ✅ Done |
| Archived Posts | ✅ Done |

### 📖 Stories (24-Hour Content)
| Feature | Status |
|---------|--------|
| Create Photo Stories | ✅ Done |
| 24-Hour Auto-Expiry | ✅ Done |
| Story Viewers List | ✅ Done |
| Emoji Reactions to Stories | ✅ Done |
| Story Polls (Vote A/B) | ✅ Done |
| Music Info Display | ✅ Done |
| Story Highlights (Permanent) | ✅ Done |

### 🎬 Reels (Short Videos)
| Feature | Status |
|---------|--------|
| Upload Short Videos | ✅ Done |
| Dedicated Reels Feed | ✅ Done |
| Like, Comment, Share Reels | ✅ Done |
| Auto-detect Video Posts | ✅ Done |

### 💬 Direct Messaging
| Feature | Status |
|---------|--------|
| 1-on-1 Private Chat | ✅ Done |
| Send Images in DMs | ✅ Done |
| Share Posts via DMs | ✅ Done |
| Message Reactions (Double-Tap ❤️) | ✅ Done |
| Read Receipts (✓ Sent / ✓✓ Seen) | ✅ Done |
| Unread Message Count | ✅ Done |

### 🔔 Notifications
| Feature | Status |
|---------|--------|
| Like Notifications | ✅ Done |
| Comment Notifications | ✅ Done |
| Reply Notifications | ✅ Done |
| Follow Notifications | ✅ Done |
| @Mention Notifications | ✅ Done |
| Story Reaction Notifications | ✅ Done |
| Real-Time Polling | ✅ Done |

### ⚙️ Settings & Privacy
| Feature | Status |
|---------|--------|
| Change Password | ✅ Done |
| Private / Public Account | ✅ Done |
| Block Users | ✅ Done |
| Delete Account | ✅ Done |

---

## 📸 Screenshots

<div align="center">

| Login Page | Feed |
|-----------|------|
| ![Login](https://via.placeholder.com/400x300/000000/ffffff?text=Login+Page) | ![Feed](https://via.placeholder.com/400x300/000000/ffffff?text=Feed+Page) |

| Profile | Messages |
|---------|---------|
| ![Profile](https://via.placeholder.com/400x300/000000/ffffff?text=Profile+Page) | ![Messages](https://via.placeholder.com/400x300/000000/ffffff?text=Messages+Page) |

</div>

> 💡 *Replace these placeholder images with actual screenshots of your app*

---

## 🛠️ Tech Stack

```
Frontend:    HTML5, CSS3 (Vanilla), JavaScript (ES6+)
Backend:     Python 3.14, Django 6.0.1
Database:    SQLite (Dev) / PostgreSQL (Production)
Storage:     Local Media (Dev) / AWS S3 / Cloudinary (Production)
UI Design:   Custom Instagram-inspired Dark Mode CSS
```

---

## 🚀 Installation & Local Setup

### Prerequisites
- Python 3.10+
- pip
- git

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/connectify.git
cd connectify
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Migrations
```bash
python manage.py migrate
```

### 5. Create Admin User
```bash
python manage.py createsuperuser
```

### 6. Run Development Server
```bash
python manage.py runserver
```

### 7. Open in Browser
```
http://127.0.0.1:8000/
```

---

## 📁 Project Structure

```
connectify/
│
├── connectify/          # Main Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── accounts/            # User auth, profiles, follow system
├── posts/               # Feed, posts, likes, comments, reels
├── stories/             # Stories, highlights, reactions, polls
├── messaging/           # Direct messages, reactions, seen
├── notifications/       # All notification types
│
├── templates/           # All HTML templates
│   ├── base.html
│   ├── accounts/
│   ├── posts/
│   ├── stories/
│   └── messaging/
│
├── static/
│   ├── css/style.css    # Full Instagram-style CSS (1900+ lines)
│   └── js/app.js        # Interactive JS (AJAX, polling, animations)
│
├── media/               # User uploaded files
├── requirements.txt
└── manage.py
```

---

## 🌐 Deployment

### Deploy to PythonAnywhere (Free)
1. Create account at [pythonanywhere.com](https://www.pythonanywhere.com)
2. Clone this repo in their Bash console
3. Set up virtualenv and install requirements
4. Configure WSGI file
5. Set `DEBUG = False` and `ALLOWED_HOSTS`
6. Done! Your site is live at `username.pythonanywhere.com`

### Deploy to Railway
1. Push to GitHub
2. Connect at [railway.app](https://railway.app)
3. Add PostgreSQL database
4. Set environment variables
5. Deploy!

---

## 🔐 Environment Variables (Production)

```env
SECRET_KEY=your-super-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:pass@host/dbname
```

---

## 🤝 Contributing

Contributions are welcome! Feel free to:

1. Fork the project
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📊 Database Schema

```
User ──── Profile (1:1)
User ──── Post (1:Many)
Post ──── PostMedia (1:Many)     # Images + Videos
Post ──── Like (Many:Many)
Post ──── Comment (1:Many)
Comment ── Comment (self, replies)
Post ──── SavedPost (Many:Many)
User ──── Follow (Many:Many)
User ──── Story (1:Many)
Story ─── StoryView (Many:Many)
Story ─── StoryReaction (Many:Many)
Story ─── StoryHighlight (Many:Many)
User ──── Thread (Many:Many)     # DMs
Thread ── Message (1:Many)
User ──── Notification (1:Many)
User ──── BlockedUser (Many:Many)
```

---

## 📝 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Rajeev Swami**
- GitHub: [@YOUR_USERNAME](https://github.com/YOUR_USERNAME)
- LinkedIn: [Your LinkedIn](https://linkedin.com/in/yourprofile)

---

## ⭐ Show Your Support

If you found this project helpful, please give it a **⭐ Star** on GitHub!

It motivates me to build more open-source projects. 🙏

---

<div align="center">

**Made with ❤️ using Django & Python**

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=flat&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat&logo=javascript&logoColor=black)

</div>

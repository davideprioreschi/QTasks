# QTasks

QTasks is an Open Source web application for project and task management, designed for individuals, teams, and developers.  
Built entirely in Python (FastAPI + SQLite) with a simple HTML/CSS frontend, it aims to provide a lightweight, extensible solution that’s ready for advanced features and AI integration in the future.

---

## **Project Goals**

- Complete management of **projects**, **tasks**, **sub-tasks**, and **attachments** in an intuitive web interface
- Simple usage for both local and small team setups
- Clean and customizable backend code
- Local, portable database that is *not* included in the repository for privacy and portability reasons
- **Extendability**: future features planned include comments, tags, granular permissions, notifications, and automations

---

## **Current Status**

- Create and manage projects
- Tasks and sub-tasks linkable to projects
- Assign tasks to specific users
- Attach files to tasks and download instantly
- User system: registration, login, SHA256 authentication
- Responsive HTML templates and clear backend/frontend separation
- Database schema initializes automatically if missing (`init_db`)
- Works on Windows / Mac / Linux

> **In development:** task comments, advanced permissions, dashboard, REST API for mobile integration.

---

## **Technologies and Packages Used**

- **Python 3.11+**
- **FastAPI**: backend API and web server
- **Uvicorn**: ASGI server for local development
- **SQLite**: lightweight and portable database
- **Jinja2**: templating engine for HTML rendering
- **HTML5, CSS3, FontAwesome**: clean frontend
- **pip**: package management
- **venv**: Python virtual environment
- **bcrypt** *(future)*: for password hashing (currently SHA256 for speed)

---


---

## **Prerequisites**

- **Python 3.11+** installed
- **Git** installed

---

## **Local Installation Steps**

1. Clone the repository  
   `git clone https://github.com/davideprioreschi/QTasks.git`

2. Enter the project folder  
   `cd QTasks`

3. (Optional: switch to the development branch)  
   `git checkout dev`

4. Create a Python virtual environment  
   `python -m venv venv`

5. Activate the virtual environment  
   `venv\Scripts\activate` # On Windows  
   `source venv/bin/activate` # On Mac/Linux

6. Install required packages  
   `pip install -r requirements.txt`

7. Start the FastAPI development server  
   `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

---

## **First Run**

- On the first run, if `db/qtasks.db` is missing, it will be **created automatically** with the full schema via `init_db.py`.
- Database files are **NOT included in the repository** (`.gitignore` applies); each user gets their own local DB.
- **Upload folders and attachments are not tracked via git** for privacy and concurrency reasons.

---

## **Development Practices**

- **All operational commands** should be run from command line or VS Code terminal with the virtual environment activated.
- Always update to the main/development branch before contributing and install latest dependencies.
- **Pull Requests:** code only, never DB or user-uploaded files.

---

## **Future Plans**

- Task comments and notifications
- Granular user permissions (Admin, Member, Guest)
- REST API integration for mobile and automations
- Bootstrap/responsive frontend interface
- AI-powered task automation and suggestions
- Tagging, advanced filters, project statistics

---

## **Contributors**

- **Davide Prioreschi** — [davidevprioreschi@gmail.com](mailto:davidevprioreschi@gmail.com) (Creator)
- **Alessio Carrara** — [alex971630@gmail.com](mailto:alex971630@gmail.com) (Core Contributor)

**We are actively looking for new contributors!**  
Fork the repo, make your improvements, and send us a Pull Request or get in touch!

---

## **Contact**

- Main repository issues: [github.com/davideprioreschi/QTasks/issues](https://github.com/davideprioreschi/QTasks/issues)
- For questions or collaboration: see contributor emails above

---

*For technical questions or suggestions, see the Issues section or email the team!*

---

**License: MIT**





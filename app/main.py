from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import Form
from fastapi.responses import RedirectResponse
from fastapi import Form, UploadFile, File, Cookie
from fastapi import Cookie
import hashlib
import sqlite3, os
from app.config import get_db_path
from app.db.init_db import create_tables


app = FastAPI()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(BASE_DIR, "db", "qtasks.db")
if not os.path.exists(DB_PATH):
    print("Database non trovato, creo lo schema...")
    create_tables()


app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "frontend", "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "frontend", "templates"))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user_id: str = Cookie(default=None)):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    utente = None
    progetti = []

    if user_id:
        # Recupera dati utente
        c.execute("SELECT nome, ruolo FROM utenti WHERE id = ?", (user_id,))
        row = c.fetchone()
        if row:
            utente = {"nome": row[0], "ruolo": row[1]}
        # Recupera progetti dove utente è owner o membro
        c.execute("""
            SELECT DISTINCT p.id, p.nome FROM progetti p
            LEFT JOIN progetti_utenti pu ON p.id = pu.progetto_id
            WHERE p.owner_id = ? OR pu.utente_id = ?
            ORDER BY p.nome
        """, (user_id, user_id))
        progetti = [{"id": r[0], "nome": r[1]} for r in c.fetchall()]
    conn.close()
    
    return templates.TemplateResponse("layout.html", {
        "request": request, 
        "utente": utente,
        "progetti": progetti,
        "title": "Dashboard QTasks"
    })


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    DB_PATH = os.path.join(BASE_DIR, "db", "qtasks.db")
    conn = sqlite3.connect(get_db_path())

    c = conn.cursor()
    c.execute("SELECT id, email, password_hash, ruolo FROM utenti WHERE email = ?", (email,))
    user = c.fetchone()
    conn.close()
    if user and hashlib.sha256(password.encode()).hexdigest() == user[2]:
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(key="user_id", value=str(user[0]), httponly=True)
        return response
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Email o password errati"})
    
@app.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
async def register_post(request: Request, nome: str = Form(...), email: str = Form(...), password: str = Form(...)):
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    try:
        # Il primo utente che si registra diventa automaticamente admin
        c.execute("SELECT COUNT(*) FROM utenti")
        user_count = c.fetchone()[0]
        ruolo = "admin" if user_count == 0 else "utente"
        
        c.execute("INSERT INTO utenti (nome, email, password_hash, ruolo) VALUES (?, ?, ?, ?)",
                  (nome, email, password_hash, ruolo))
        conn.commit()
        conn.close()
        return templates.TemplateResponse("register.html", {"request": request, "success": f"Utente {nome} registrato con successo come {ruolo}!"})
    except sqlite3.IntegrityError:
        conn.close()
        return templates.TemplateResponse("register.html", {"request": request, "error": "Email già esistente!"})
    
@app.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("user_id")
    return response

@app.post("/crea_progetto")
async def crea_progetto_post(
    nome_progetto: str = Form(...),
    membri: list = Form([]),
    user_id: str = Cookie(default=None)
):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("INSERT INTO progetti (nome, owner_id) VALUES (?, ?)", (nome_progetto, user_id))
    progetto_id = c.lastrowid
    # L’owner è sempre membro “di default”
    c.execute("INSERT INTO progetti_utenti (progetto_id, utente_id) VALUES (?, ?)", (progetto_id, int(user_id)))
    for membro_id in membri:
        c.execute("INSERT OR IGNORE INTO progetti_utenti (progetto_id, utente_id) VALUES (?, ?)", (progetto_id, int(membro_id)))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=302)



@app.post("/crea_progetto")
async def crea_progetto(nome_progetto: str = Form(...), user_id: str = Cookie(default=None)):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("INSERT INTO progetti (nome, owner_id) VALUES (?, ?)", (nome_progetto, user_id))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=302)

@app.get("/progetto/{progetto_id}", response_class=HTMLResponse)
async def visualizza_progetto(request: Request, progetto_id: int, user_id: str = Cookie(default=None)):
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Controlla permesso: owner o membro
    c.execute("""
        SELECT 1 FROM progetti p
        LEFT JOIN progetti_utenti pu ON p.id = pu.progetto_id
        WHERE p.id = ? AND (p.owner_id = ? OR pu.utente_id = ?)
    """, (progetto_id, user_id, user_id))
    if not c.fetchone():
        conn.close()
        return RedirectResponse("/", status_code=302)

    # Info progetto
    c.execute("SELECT nome FROM progetti WHERE id = ?", (progetto_id,))
    progetto = c.fetchone()
    if not progetto:
        conn.close()
        return RedirectResponse("/", status_code=302)

    # Task del progetto (includi anche campo assegnato_a e scadenza)
    c.execute("""SELECT id, titolo, descrizione, stato, parent_id, assegnato_a, scadenza 
                 FROM tasks WHERE progetto_id = ?""", (progetto_id,))
    tasks = []
    for r in c.fetchall():
        tasks.append({
            "id": r[0],
            "titolo": r[1],
            "descrizione": r[2],
            "stato": r[3],
            "parent_id": r[4],
            "assegnato_a": r[5],
            "scadenza": r[6]
        })

    # Lista membri del progetto (owner + tabella)
    c.execute("""
        SELECT DISTINCT u.id, u.nome FROM utenti u
        INNER JOIN progetti_utenti pu ON u.id = pu.utente_id
        WHERE pu.progetto_id = ?
        UNION
        SELECT u.id, u.nome FROM utenti u
        INNER JOIN progetti p ON u.id = p.owner_id
        WHERE p.id = ?
    """, (progetto_id, progetto_id))
    membri_progetto = [{"id": r[0], "nome": r[1]} for r in c.fetchall()]

    # Allegati per ogni task
    allegati_per_task = {}
    for t in tasks:
        c.execute("SELECT filename, filepath FROM allegati WHERE task_id = ?", (t["id"],))
        allegati = [{"filename": r[0], "filepath": r[1]} for r in c.fetchall()]
        allegati_per_task[t["id"]] = allegati

    conn.close()

    return templates.TemplateResponse("progetto.html", {
        "request": request,
        "progetto_nome": progetto[0],
        "progetto_id": progetto_id,
        "tasks": tasks,
        "membri_progetto": membri_progetto,
        "allegati_per_task": allegati_per_task
    })


@app.post("/crea_task")
async def crea_task(
    progetto_id: int = Form(...),
    titolo: str = Form(...),
    descrizione: str = Form(""),
    stato: str = Form(...),
    parent_id: str = Form(""),
    assegnato_a: str = Form(""),
    scadenza: str = Form(""),
    user_id: str = Cookie(default=None),
    allegato: UploadFile = File(None)
):
    # ... controllo login (+ permessi) ...
    parent_id_val = int(parent_id) if parent_id else None
    assegnato_val = int(assegnato_a) if assegnato_a else None
    scadenza_val = scadenza if scadenza else None

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Permessi su progetto -> come da tuo codice!

    c.execute("""
        INSERT INTO tasks (
            titolo, descrizione, progetto_id, autore_id, stato, parent_id, assegnato_a, scadenza
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (titolo, descrizione, progetto_id, user_id, stato, parent_id_val, assegnato_val, scadenza_val))
    task_id = c.lastrowid

    # **Gestione allegato**
    if allegato is not None and allegato.filename:
        upload_dir = os.path.join(BASE_DIR, "frontend", "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, allegato.filename)
        with open(filepath, "wb") as f:
            f.write(await allegato.read())
        # Questa variabile va usata per il DB! (slash / e sempre con lo slash iniziale)
        db_filepath = f"/static/uploads/{allegato.filename}"
        # USA db_filepath NEL DATABASE! NON filepath
        c.execute("""
            INSERT INTO allegati (task_id, filename, filepath, uploaded_by)
            VALUES (?, ?, ?, ?)
        """, (task_id, allegato.filename, db_filepath, user_id))

    conn.commit()
    conn.close()
    return RedirectResponse(f"/progetto/{progetto_id}", status_code=302)



@app.post("/elimina_task")
async def elimina_task(
    task_id: int = Form(...),
    progetto_id: int = Form(...),
    user_id: str = Cookie(default=None)
):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Ricava progetto_id dal task
    c.execute("SELECT progetto_id FROM tasks WHERE id = ?", (task_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return RedirectResponse("/", status_code=302)
    progetto_id_db = row[0]
    # Controllo permesso: owner o membro
    c.execute("""
        SELECT 1 FROM progetti p
        LEFT JOIN progetti_utenti pu ON p.id = pu.progetto_id
        WHERE p.id = ? AND (p.owner_id = ? OR pu.utente_id = ?)
    """, (progetto_id_db, user_id, user_id))
    if not c.fetchone():
        conn.close()
        return RedirectResponse("/", status_code=302)

    # Eliminazione task (ricorsiva come già fatto)
    def elimina_cascade(id):
        c.execute("SELECT id FROM tasks WHERE parent_id = ?", (id,))
        figli = c.fetchall()
        for f in figli:
            elimina_cascade(f[0])
        c.execute("DELETE FROM tasks WHERE id = ?", (id,))
    
    elimina_cascade(task_id)
    conn.commit()
    conn.close()
    return RedirectResponse(f"/progetto/{progetto_id_db}", status_code=302)



@app.get("/modifica_task/{task_id}", response_class=HTMLResponse)
async def modifica_task_get(request: Request, task_id: int, progetto_id: int = None, user_id: str = Cookie(default=None)):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Ricava progetto_id dal task
    c.execute("SELECT progetto_id FROM tasks WHERE id = ?", (task_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return RedirectResponse("/", status_code=302)
    progetto_id = row[0]

    # Permessi
    c.execute("""
        SELECT 1 FROM progetti p
        LEFT JOIN progetti_utenti pu ON p.id = pu.progetto_id
        WHERE p.id = ? AND (p.owner_id = ? OR pu.utente_id = ?)
    """, (progetto_id, user_id, user_id))
    if not c.fetchone():
        conn.close()
        return RedirectResponse("/", status_code=302)

    # Task attuale
    c.execute("""
        SELECT titolo, descrizione, stato, parent_id, assegnato_a, scadenza 
        FROM tasks WHERE id = ?
    """, (task_id,))
    task = c.fetchone()
    if not task:
        conn.close()
        return RedirectResponse(f"/progetto/{progetto_id}", status_code=302)

    # Membri progetto
    c.execute("""
        SELECT DISTINCT u.id, u.nome FROM utenti u
        INNER JOIN progetti_utenti pu ON u.id = pu.utente_id
        WHERE pu.progetto_id = ?
        UNION
        SELECT u.id, u.nome FROM utenti u
        INNER JOIN progetti p ON u.id = p.owner_id
        WHERE p.id = ?
    """, (progetto_id, progetto_id))
    membri_progetto = [{"id": r[0], "nome": r[1]} for r in c.fetchall()]

    # Altri task per parent_id
    c.execute("SELECT id, titolo FROM tasks WHERE progetto_id = ? AND id != ?", (progetto_id, task_id))
    all_tasks = [{"id": r[0], "titolo": r[1]} for r in c.fetchall()]

    # Allegati
    c.execute("SELECT id, filename, filepath FROM allegati WHERE task_id = ?", (task_id,))
    allegati = [{"id": r[0], "filename": r[1], "filepath": r[2]} for r in c.fetchall()]

    conn.close()
    return templates.TemplateResponse("modifica_task.html", {
        "request": request,
        "task_id": task_id,
        "progetto_id": progetto_id,
        "titolo": task[0],
        "descrizione": task[1],
        "stato": task[2],
        "parent_id": task[3],
        "assegnato_a": task[4],
        "scadenza": task[5],
        "membri_progetto": membri_progetto,
        "all_tasks": all_tasks,
        "allegati": allegati
    })



@app.post("/modifica_task/{task_id}")
async def modifica_task_post(
    task_id: int,
    progetto_id: int = Form(...),
    titolo: str = Form(...),
    descrizione: str = Form(...),
    stato: str = Form(...),
    parent_id: str = Form(""),
    assegnato_a: str = Form(""),
    scadenza: str = Form(""),
    user_id: str = Cookie(default=None),
    allegato: UploadFile = File(None)
):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    parent_id_val = int(parent_id) if parent_id else None
    assegnato_val = int(assegnato_a) if assegnato_a else None
    scadenza_val = scadenza if scadenza else None

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Permessi
    c.execute("""
        SELECT 1 FROM progetti p
        LEFT JOIN progetti_utenti pu ON p.id = pu.progetto_id
        WHERE p.id = ? AND (p.owner_id = ? OR pu.utente_id = ?)
    """, (progetto_id, user_id, user_id))
    if not c.fetchone():
        conn.close()
        return RedirectResponse("/", status_code=302)

    # Modifica task
    c.execute("""
        UPDATE tasks SET titolo = ?, descrizione = ?, stato = ?, parent_id = ?, assegnato_a = ?, scadenza = ?
        WHERE id = ?
    """, (titolo, descrizione, stato, parent_id_val, assegnato_val, scadenza_val, task_id))

    # Upload allegato (opzionale)
    if allegato is not None and allegato.filename:
        upload_dir = os.path.join(BASE_DIR, "frontend", "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, allegato.filename)
        with open(filepath, "wb") as f:
            f.write(await allegato.read())
        # Questa variabile va usata per il DB! (slash / e sempre con lo slash iniziale)
        db_filepath = f"/static/uploads/{allegato.filename}"
        # USA db_filepath NEL DATABASE! NON filepath
        c.execute("""
            INSERT INTO allegati (task_id, filename, filepath, uploaded_by)
            VALUES (?, ?, ?, ?)
        """, (task_id, allegato.filename, db_filepath, user_id))





    conn.commit()
    conn.close()
    return RedirectResponse(f"/progetto/{progetto_id}", status_code=302)


@app.post("/elimina_progetto")
async def elimina_progetto(
    progetto_id: int = Form(...),
    user_id: str = Cookie(default=None)
):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Controllo permessi: owner o membro
    c.execute("""
        SELECT 1 FROM progetti p
        LEFT JOIN progetti_utenti pu ON p.id = pu.progetto_id
        WHERE p.id = ? AND (p.owner_id = ? OR pu.utente_id = ?)
    """, (progetto_id, user_id, user_id))
    if not c.fetchone():
        conn.close()
        return RedirectResponse("/", status_code=302)
    
    c.execute("DELETE FROM tasks WHERE progetto_id = ?", (progetto_id,))
    c.execute("DELETE FROM progetti_utenti WHERE progetto_id = ?", (progetto_id,))
    c.execute("DELETE FROM progetti WHERE id = ?", (progetto_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=302)


@app.get("/modifica_progetto/{progetto_id}", response_class=HTMLResponse)
async def modifica_progetto_get(request: Request, progetto_id: int, user_id: str = Cookie(default=None)):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Controllo permessi: owner o membro
    c.execute("""
        SELECT 1 FROM progetti p
        LEFT JOIN progetti_utenti pu ON p.id = pu.progetto_id
        WHERE p.id = ? AND (p.owner_id = ? OR pu.utente_id = ?)
    """, (progetto_id, user_id, user_id))
    if not c.fetchone():
        conn.close()
        return RedirectResponse("/", status_code=302)
    
    c.execute("SELECT nome FROM progetti WHERE id = ?", (progetto_id,))
    progetto = c.fetchone()
    # Tutti gli utenti
    c.execute("SELECT id, nome FROM utenti")
    tutti_utenti = [{"id": r[0], "nome": r[1]} for r in c.fetchall()]
    # Membri attuali
    c.execute("SELECT utente_id FROM progetti_utenti WHERE progetto_id = ?", (progetto_id,))
    membri_attuali = [r[0] for r in c.fetchall()]
    conn.close()
    if not progetto:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("modifica_progetto.html", {
        "request": request,
        "progetto_id": progetto_id,
        "nome": progetto[0],
        "tutti_utenti": tutti_utenti,
        "membri_attuali": membri_attuali
    })



@app.post("/modifica_progetto/{progetto_id}")
async def modifica_progetto_post(
    progetto_id: int,
    nome: str = Form(...),
    membri: list = Form([]),
    user_id: str = Cookie(default=None)
):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Controllo permessi: owner o membro
    c.execute("""
        SELECT 1 FROM progetti p
        LEFT JOIN progetti_utenti pu ON p.id = pu.progetto_id
        WHERE p.id = ? AND (p.owner_id = ? OR pu.utente_id = ?)
    """, (progetto_id, user_id, user_id))
    if not c.fetchone():
        conn.close()
        return RedirectResponse("/", status_code=302)
    
    # Aggiorna nome progetto
    c.execute("UPDATE progetti SET nome = ? WHERE id = ?", (nome, progetto_id))
    # Rimuovi tutti i membri attuali
    c.execute("DELETE FROM progetti_utenti WHERE progetto_id = ?", (progetto_id,))
    # Aggiungi i nuovi membri selezionati
    for membro_id in membri:
        c.execute("INSERT INTO progetti_utenti (progetto_id, utente_id) VALUES (?, ?)", (progetto_id, int(membro_id)))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=302)



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
from fastapi.responses import StreamingResponse
import csv
from io import StringIO
import smtplib


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
    if user_id:
        c.execute("SELECT nome, ruolo FROM utenti WHERE id = ?", (user_id,))
        row = c.fetchone()
        if row:
            utente = {"nome": row[0], "ruolo": row[1]}
    c.execute("SELECT id, nome FROM utenti")
    utenti_rete = [{"id": r[0], "nome": r[1]} for r in c.fetchall()]
    c.execute("SELECT id, nome, owner_id, capo_progetto_id FROM progetti")
    progetti_rete = [{"id": r[0], "nome": r[1], "owner_id": r[2], "capo_progetto_id": r[3]} for r in c.fetchall()]
    c.execute("""
        SELECT DISTINCT p.id, p.nome, p.owner_id, p.capo_progetto_id FROM progetti p
        LEFT JOIN progetti_utenti pu ON p.id = pu.progetto_id
        WHERE p.owner_id = ? OR pu.utente_id = ?
        ORDER BY p.nome
    """, (user_id, user_id))
    progetti = [{"id": r[0], "nome": r[1], "owner_id": r[2], "capo_progetto_id": r[3]} for r in c.fetchall()]

    ids_miei_progetti = [p["id"] for p in progetti]
    c.execute("SELECT progetto_id FROM progetti_richieste WHERE utente_id=? AND stato='pending'", (user_id,))
    richieste_inviate = [r[0] for r in c.fetchall()]
    richieste = []
    if utente and user_id:
        c.execute("SELECT id FROM progetti WHERE capo_progetto_id=? OR owner_id=?", (user_id, user_id))
        progetti_gestiti = [r[0] for r in c.fetchall()]
        for pid in progetti_gestiti:
            c.execute(
                """SELECT pr.id, pr.utente_id, u.nome, pr.stato, pr.data_request, pr.progetto_id, p.nome
                   FROM progetti_richieste pr
                   JOIN utenti u ON pr.utente_id = u.id
                   JOIN progetti p ON pr.progetto_id = p.id
                   WHERE pr.progetto_id = ? AND pr.stato='pending'""", (pid,))
            richieste += [{"id": r[0], "utente_id": r[1], "nome": r[2], "stato": r[3], "data": r[4],
                           "progetto_id": r[5], "progetto_nome": r[6]} for r in c.fetchall()]

    # ---> Notifiche admin per la campanella
    c.execute('''CREATE TABLE IF NOT EXISTS notifiche_admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titolo TEXT NOT NULL,
        testo TEXT NOT NULL,
        letto INTEGER DEFAULT 0,
        data_creazione TEXT DEFAULT CURRENT_TIMESTAMP
    );''')
    c.execute("SELECT id, titolo, testo, letto, data_creazione FROM notifiche_admin ORDER BY data_creazione DESC LIMIT 20")
    notifiche_admin = [{
        "id": r[0], "titolo": r[1], "testo": r[2], "letto": r[3], "data": r[4]
    } for r in c.fetchall()]
    num_notifiche_admin = sum(1 for n in notifiche_admin if n["letto"]==0)
    conn.close()
    return templates.TemplateResponse("layout.html", {
        "request": request,
        "utente": utente,
        "user_id": user_id,
        "progetti": progetti,
        "ids_miei_progetti": ids_miei_progetti,
        "utenti_rete": utenti_rete,
        "progetti_rete": progetti_rete,
        "richieste_inviate": richieste_inviate,
        "richieste": richieste,
        "title": "Dashboard QTasks",
        "notifiche_admin": notifiche_admin,
        "num_notifiche_admin": num_notifiche_admin
    })


def invia_notifica_admin(oggetto, messaggio):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT email FROM utenti WHERE ruolo='admin' ORDER BY id LIMIT 1")
    admin = c.fetchone()
    c.execute("SELECT * FROM configurazione_email LIMIT 1")
    config = c.fetchone()
    conn.close()
    if not admin or not config:
        return False
    admin_email = admin[0]
    smtp_host, smtp_port, smtp_username, smtp_password, sender_email, use_tls, use_ssl = config[1:]
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(messaggio)
        msg['Subject'] = oggetto
        msg['From'] = sender_email
        msg['To'] = admin_email
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            if use_tls:
                server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, [admin_email], msg.as_string())
        server.quit()
        # (Extra: log su tabella notifiche per dashboard)
        log_notifica_admin(oggetto, messaggio)
        return True
    except Exception as e:
        print(e)
        return False
    
@app.post("/notifica_admin/{notifica_id}/leggi")
async def leggi_notifica_admin(notifica_id: int, user_id: str = Cookie(default=None)):
    # Solo admin
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT ruolo FROM utenti WHERE id = ?", (user_id,))
    ruolo = c.fetchone()[0] if user_id else None
    if ruolo != "admin":
        conn.close()
        return RedirectResponse("/", status_code=302)
    c.execute("UPDATE notifiche_admin SET letto = 1 WHERE id = ?", (notifica_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=302)


def log_notifica_admin(titolo, testo):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS notifiche_admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titolo TEXT NOT NULL,
        testo TEXT NOT NULL,
        letto INTEGER DEFAULT 0,
        data_creazione TEXT DEFAULT CURRENT_TIMESTAMP
    );''')
    c.execute("INSERT INTO notifiche_admin (titolo, testo) VALUES (?,?)", (titolo, testo))
    conn.commit()
    conn.close()


@app.get("/test_email")
async def test_email(user_id: str = Cookie(default=None)):
    # 1. Recupera la mail dell'utente corrente
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT email FROM utenti WHERE id=?", (user_id,))
    user = c.fetchone()
    recipient = user[0] if user else None

    # 2. Recupera la configurazione smtp mittente
    c.execute("SELECT * FROM configurazione_email LIMIT 1")
    config = c.fetchone()
    conn.close()
    if not recipient:
        return {"result": "Utente loggato non trovato"}
    if not config:
        return {"result": "Nessuna configurazione email"}

    smtp_host, smtp_port, smtp_username, smtp_password, sender_email, use_tls, use_ssl = config[1:]
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText("Questa è una mail di test dal sistema QTasks.\nSe la ricevi, le notifiche funzionano! :)")
        msg['Subject'] = "Test notifica QTasks"
        msg['From'] = sender_email
        msg['To'] = recipient

        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            if use_tls:
                server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, [recipient], msg.as_string())
        server.quit()
        return {"result": f"Email di test inviata a {recipient}"}
    except Exception as e:
        return {"result": f"Errore invio email: {e}"}





@app.post("/admin/elimina_utente")
async def elimina_utente(utente_id: int = Form(...), user_id: str = Cookie(default=None)):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT ruolo FROM utenti WHERE id = ?", (user_id,))
    ruolo = c.fetchone()[0] if user_id else None
    # Recupera info utente eliminato
    c.execute("SELECT nome, email FROM utenti WHERE id = ?", (utente_id,))
    ut = c.fetchone()
    nome_del = ut[0] if ut else ''
    email_del = ut[1] if ut else ''
    if ruolo != "admin":
        conn.close()
        return RedirectResponse("/", status_code=302)
    c.execute("DELETE FROM progetti_utenti WHERE utente_id = ?", (utente_id,))
    c.execute("DELETE FROM progetti WHERE owner_id = ?", (utente_id,))
    c.execute("DELETE FROM utenti WHERE id = ?", (utente_id,))
    conn.commit()
    conn.close()
    # Notifica admin
    invia_notifica_admin(
        "Utente eliminato",
        f"L'utente '{nome_del}' ({email_del}, ID: {utente_id}) è stato eliminato dall'amministratore."
    )
    return RedirectResponse("/", status_code=302)



@app.post("/admin/elimina_progetto")
async def elimina_progetto_admin(progetto_id: int = Form(...), user_id: str = Cookie(default=None)):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT ruolo FROM utenti WHERE id = ?", (user_id,))
    ruolo = c.fetchone()[0] if user_id else None
    if ruolo != "admin":
        conn.close()
        return RedirectResponse("/", status_code=302)
    # Rimozione cascata di tutto ciò che dipende dal progetto
    c.execute("DELETE FROM tasks WHERE progetto_id = ?", (progetto_id,))
    c.execute("DELETE FROM progetti_utenti WHERE progetto_id = ?", (progetto_id,))
    c.execute("DELETE FROM progetti WHERE id = ?", (progetto_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=302)

@app.post("/progetto/{progetto_id}/tasks/import")
async def import_tasks_csv(progetto_id: int, file: UploadFile = File(...), user_id: str = Cookie(default=None)):
    import csv
    db_path = get_db_path()
    content = await file.read()
    lines = content.decode("utf-8").splitlines()
    reader = csv.DictReader(lines)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for row in reader:
        c.execute("""
            INSERT INTO tasks
            (titolo, descrizione, stato, parent_id, assegnato_a, scadenza, priority, position, progetto_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (row["titolo"], row["descrizione"], row["stato"], row["parent_id"] or None, row["assegnato_a"] or None,
              row["scadenza"], int(row.get("priority", 1)), int(row.get("position", 0)), progetto_id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/progetto/{progetto_id}", status_code=302)


@app.get("/progetto/{progetto_id}/tasks/export")
async def export_tasks_csv(progetto_id: int, user_id: str = Cookie(default=None)):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, titolo, descrizione, stato, parent_id, assegnato_a, scadenza, priority, position FROM tasks WHERE progetto_id=?", (progetto_id,))
    tasks = c.fetchall()
    conn.close()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["id","titolo","descrizione","stato","parent_id","assegnato_a","scadenza","priority","position"])
    for t in tasks:
        writer.writerow(t)
    si.seek(0)
    return StreamingResponse(si, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=tasks_progetto_{progetto_id}.csv"})


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
        c.execute("SELECT COUNT(*) FROM utenti WHERE ruolo='admin'")
        admin_count = c.fetchone()[0]
        ruolo = "admin" if admin_count == 0 else "utente"
        c.execute("INSERT INTO utenti (nome, email, password_hash, ruolo) VALUES (?, ?, ?, ?)",
                  (nome, email, password_hash, ruolo))
        conn.commit()
        c.execute("SELECT id FROM utenti WHERE email = ?", (email,))
        user_id = c.fetchone()[0]
        conn.close()
        # Notifica all'admin SOLO se non è il primissimo admin
        if ruolo != "admin":
            invia_notifica_admin(
                "Nuova registrazione utente",
                f"L'utente '{nome}' ({email}) si è appena registrato nel sistema."
            )
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(key="user_id", value=str(user_id), httponly=True)
        # Se primo admin, reindirizza subito al setup configurazione email
        if ruolo == "admin" and admin_count == 0:
            return RedirectResponse("/configura_email", status_code=302)
        return response
    except sqlite3.IntegrityError:
        conn.close()
        return templates.TemplateResponse("register.html", {"request": request, "error": "Email già esistente!"})


    
@app.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("user_id")
    return response


@app.get("/progetti/richieste", response_class=HTMLResponse)
async def richieste_progetti(request: Request, user_id: str = Cookie(default=None)):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Trova progetti dove l'utente è capo progetto o owner
    c.execute("""
        SELECT id FROM progetti WHERE capo_progetto_id=? OR owner_id=?
    """, (user_id, user_id))
    progetti_gestiti = [r[0] for r in c.fetchall()]
    # Recupera richieste pendenti per questi progetti
    richieste = []
    for pid in progetti_gestiti:
        c.execute("""
            SELECT pr.id, pr.utente_id, u.nome, pr.stato, pr.data_request, pr.progetto_id, p.nome
            FROM progetti_richieste pr
            JOIN utenti u ON pr.utente_id = u.id
            JOIN progetti p ON pr.progetto_id = p.id
            WHERE pr.progetto_id = ? AND pr.stato='pending'
        """, (pid,))
        richieste += [{"id": r[0], "utente_id": r[1], "nome": r[2], "stato": r[3], "data": r[4],
                      "progetto_id": r[5], "progetto_nome": r[6]} for r in c.fetchall()]
    conn.close()
    return templates.TemplateResponse("layout.html", {
        "request": request,
        # ... altre variabili che servono alla dashboard ...
        "richieste": richieste,
        "title": "Dashboard QTasks"
    })


@app.post("/progetti/richiesta", response_class=HTMLResponse)
async def invia_richiesta_progetto(request: Request, progetto_id: int = Form(...), user_id: str = Cookie(default=None)):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM progetti_richieste WHERE utente_id=? AND progetto_id=? AND stato='pending'",
             (user_id, progetto_id))
    msg = None
    if c.fetchone()[0] > 0:
        msg = "Hai già richiesto l'accesso: la tua richiesta è in attesa di approvazione."
    else:
        c.execute("INSERT INTO progetti_richieste (utente_id, progetto_id, stato) VALUES (?, ?, ?)",
                (user_id, progetto_id, 'pending'))
        conn.commit()
        msg = "Richiesta inviata! Attendi che il capo progetto la approvi."
        # Recupera info utente e progetto (FIX)
        c.execute("SELECT nome FROM utenti WHERE id=?", (user_id,))
        row = c.fetchone()
        nome_utente = row[0] if row else ''
        c.execute("SELECT nome FROM progetti WHERE id=?", (progetto_id,))
        row = c.fetchone()
        nome_proj = row[0] if row else ''
        invia_notifica_admin(
            "Nuova richiesta di ingresso progetto",
            f"L'utente '{nome_utente}' ha richiesto di entrare nel progetto '{nome_proj}' (ID {progetto_id})."
        )


    # Recupera variabili per render template (N.B. il resto invariato)
    c.execute("SELECT nome, ruolo FROM utenti WHERE id = ?", (user_id,))
    row = c.fetchone()
    utente = {"nome": row[0], "ruolo": row[1]} if row else None
    c.execute("SELECT id, nome FROM utenti")
    utenti_rete = [{"id": r[0], "nome": r[1]} for r in c.fetchall()]
    c.execute("SELECT id, nome, owner_id, capo_progetto_id FROM progetti")
    progetti_rete = [{"id": r[0], "nome": r[1], "owner_id": r[2], "capo_progetto_id": r[3]} for r in c.fetchall()]
    c.execute("""
       SELECT DISTINCT p.id, p.nome, p.owner_id, p.capo_progetto_id FROM progetti p
       LEFT JOIN progetti_utenti pu ON p.id = pu.progetto_id
       WHERE p.owner_id = ? OR pu.utente_id = ?
       ORDER BY p.nome
    """, (user_id, user_id))
    progetti = [{"id": r[0], "nome": r[1], "owner_id": r[2], "capo_progetto_id": r[3]} for r in c.fetchall()]
    ids_miei_progetti = [p["id"] for p in progetti]
    c.execute("SELECT progetto_id FROM progetti_richieste WHERE utente_id=? AND stato='pending'", (user_id,))
    richieste_inviate = [r[0] for r in c.fetchall()]
    richieste = []
    if utente and user_id:
        c.execute("SELECT id FROM progetti WHERE capo_progetto_id=? OR owner_id=?", (user_id, user_id))
        progetti_gestiti = [r[0] for r in c.fetchall()]
        for pid in progetti_gestiti:
            c.execute(
                """SELECT pr.id, pr.utente_id, u.nome, pr.stato, pr.data_request, pr.progetto_id, p.nome
                   FROM progetti_richieste pr
                   JOIN utenti u ON pr.utente_id = u.id
                   JOIN progetti p ON pr.progetto_id = p.id
                   WHERE pr.progetto_id = ? AND pr.stato='pending'""", (pid,))
            richieste += [{"id": r[0], "utente_id": r[1], "nome": r[2], "stato": r[3], "data": r[4],
                           "progetto_id": r[5], "progetto_nome": r[6]} for r in c.fetchall()]
    conn.close()
    return templates.TemplateResponse("layout.html", {
        "request": request,
        "utente": utente,
        "user_id": user_id,
        "progetti": progetti,
        "ids_miei_progetti": ids_miei_progetti,
        "utenti_rete": utenti_rete,
        "progetti_rete": progetti_rete,
        "richieste_inviate": richieste_inviate,
        "richieste": richieste,
        "successo_richiesta": msg,
        "title": "Dashboard QTasks"
    })






@app.post("/progetti/richiesta/{richiesta_id}/accetta")
async def accetta_richiesta(richiesta_id: int, user_id: str = Cookie(default=None)):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Trova utente e progetto associati
    c.execute("SELECT utente_id, progetto_id FROM progetti_richieste WHERE id=?", (richiesta_id,))
    r = c.fetchone()
    if not r:
        conn.close()
        return RedirectResponse("/", status_code=302)
    utente_id, progetto_id = r
    # Aggiorna stato richiesta
    c.execute("UPDATE progetti_richieste SET stato='accepted' WHERE id=?", (richiesta_id,))
    # Aggiungi utente alla tabella membri progetto con ruolo base (None o "Utente")
    c.execute("INSERT OR IGNORE INTO progetti_utenti (progetto_id, utente_id, ruolo_id) VALUES (?, ?, NULL)",
              (progetto_id, utente_id))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=302)

@app.post("/progetti/richiesta/{richiesta_id}/rifiuta")
async def rifiuta_richiesta(richiesta_id: int, user_id: str = Cookie(default=None)):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("UPDATE progetti_richieste SET stato='rejected' WHERE id=?", (richiesta_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=302)


@app.post("/progetti/{progetto_id}/ruoli")
async def crea_ruolo(progetto_id: int, nome: str = Form(...), permessi_json: str = Form(...), user_id: str = Cookie(default=None)):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("INSERT INTO ruoli (progetto_id, nome, permessi_json) VALUES (?, ?, ?)",
              (progetto_id, nome, permessi_json))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/progetto/{progetto_id}/gestione", status_code=302)


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
    c.execute("INSERT INTO progetti (nome, owner_id, capo_progetto_id) VALUES (?, ?, ?)", (nome_progetto, user_id, user_id))
    progetto_id = c.lastrowid
    c.execute("INSERT INTO progetti_utenti (progetto_id, utente_id) VALUES (?, ?)", (progetto_id, int(user_id)))
    for membro_id in membri:
        c.execute("INSERT OR IGNORE INTO progetti_utenti (progetto_id, utente_id) VALUES (?, ?)", (progetto_id, int(membro_id)))
    conn.commit()
    conn.close()
    # Notifica admin
    invia_notifica_admin(
        "Nuovo progetto creato",
        f"Il progetto '{nome_progetto}' è stato creato dall'utente con ID {user_id}."
    )
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

    # Controlla permessi
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

    # Recupera tasks con priority/position
    c.execute("""
        SELECT id, titolo, descrizione, stato, parent_id, assegnato_a, scadenza, priority, position 
        FROM tasks 
        WHERE progetto_id = ?
        ORDER BY (stato='completed'), priority DESC, position ASC, id ASC
    """, (progetto_id,))
    tasks = []
    for r in c.fetchall():
        tasks.append({
            "id": r[0],
            "titolo": r[1],
            "descrizione": r[2],
            "stato": r[3],
            "parent_id": r[4],
            "assegnato_a": r[5],
            "scadenza": r[6],
            "priority": r[7],
            "position": r[8]
        })

    # Lista membri del progetto
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
        allegati = [{"filename": a[0], "filepath": a[1]} for a in c.fetchall()]
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
    priority: int = Form(1),
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

    c.execute("""
        INSERT INTO tasks (
            titolo, descrizione, progetto_id, autore_id, stato, parent_id, assegnato_a, scadenza, priority
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (titolo, descrizione, progetto_id, user_id, stato, parent_id_val, assegnato_val, scadenza_val, priority))
    task_id = c.lastrowid

    # **Gestione allegato**
    if allegato is not None and allegato.filename:
        upload_dir = os.path.join(BASE_DIR, "frontend", "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, allegato.filename)
        with open(filepath, "wb") as f:
            f.write(await allegato.read())
        db_filepath = f"/static/uploads/{allegato.filename}"
        c.execute("""
            INSERT INTO allegati (task_id, filename, filepath, uploaded_by)
            VALUES (?, ?, ?, ?)
        """, (task_id, allegato.filename, db_filepath, user_id))

    conn.commit()
    conn.close()
    return RedirectResponse(f"/progetto/{progetto_id}", status_code=302)



@app.post("/task/{task_id}/toggle_complete")
async def toggle_task_complete(task_id: int, user_id: str = Cookie(default=None)):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT stato FROM tasks WHERE id=?", (task_id,))
    stato = c.fetchone()
    if not stato:
        conn.close()
        return {"ok": False}
    nuovo_stato = 'todo' if stato[0] == 'completed' else 'completed'
    c.execute("UPDATE tasks SET stato=? WHERE id=?", (nuovo_stato, task_id))
    conn.commit()
    conn.close()
    return {"ok": True, "new_state": nuovo_stato}

@app.post("/task/{task_id}/set_priority")
async def set_task_priority(task_id: int, priority: int = Form(...), user_id: str = Cookie(default=None)):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("UPDATE tasks SET priority=? WHERE id=?", (priority, task_id))
    conn.commit()
    conn.close()
    return RedirectResponse(f"/progetto/{request.query_params.get('progetto_id')}", status_code=302)


@app.post("/task/{task_id}/set_position")
async def set_task_position(task_id: int, position: int = Form(...), user_id: str = Cookie(default=None)):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("UPDATE tasks SET position=? WHERE id=?", (position, task_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/configura_email", response_class=HTMLResponse)
async def configura_email_get(request: Request, user_id: str = Cookie(default=None)):
    # (Opzionale) potresti qui accettare solo admin
    return templates.TemplateResponse("configura_email.html", {"request": request})

@app.post("/configura_email", response_class=HTMLResponse)
async def configura_email_post(request: Request,
    smtp_host: str = Form(...),
    smtp_port: int = Form(...),
    smtp_username: str = Form(...),
    smtp_password: str = Form(...),
    sender_email: str = Form(...),
    use_tls: int = Form(1),
    use_ssl: int = Form(0),
    user_id: str = Cookie(default=None)):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("DELETE FROM configurazione_email;") # Ne manteniamo solo uno
    c.execute(
        "INSERT INTO configurazione_email (id, smtp_host, smtp_port, smtp_username, smtp_password, sender_email, use_tls, use_ssl) VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
        (smtp_host, smtp_port, smtp_username, smtp_password, sender_email, use_tls, use_ssl)
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=302)




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
    # Recupera nome progetto per log
    c.execute("SELECT nome FROM progetti WHERE id = ?", (progetto_id,))
    row = c.fetchone()
    nome_proj = row[0] if row else "(sconosciuto)"
    # Permessi (già presenti)
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
    # Notifica admin
    invia_notifica_admin(
        "Progetto eliminato",
        f"Il progetto '{nome_proj}' (ID: {progetto_id}) è stato eliminato dall'utente con ID {user_id}."
    )
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



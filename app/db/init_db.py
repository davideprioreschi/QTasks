import os
import sqlite3

def create_tables():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "db", "qtasks.db")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Utenti
    c.execute('''
        CREATE TABLE IF NOT EXISTS utenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            ruolo TEXT NOT NULL  -- admin, utente, etc
        );
    ''')

    # Ruoli personalizzati (per progetto)
    c.execute('''
        CREATE TABLE IF NOT EXISTS ruoli (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            progetto_id INTEGER,
            nome TEXT NOT NULL,
            permessi_json TEXT NOT NULL, -- es: {"crea_task": true, ...}
            FOREIGN KEY (progetto_id) REFERENCES progetti(id)
        );
    ''')

    # Progetti
    c.execute('''
        CREATE TABLE IF NOT EXISTS progetti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            capo_progetto_id INTEGER NOT NULL, -- modificabile
            FOREIGN KEY (owner_id) REFERENCES utenti(id),
            FOREIGN KEY (capo_progetto_id) REFERENCES utenti(id)
        );
    ''')

    # Progetti-Utenti (membri dei progetti, con ruolo)
    c.execute('''
        CREATE TABLE IF NOT EXISTS progetti_utenti (
            progetto_id INTEGER,
            utente_id INTEGER,
            ruolo_id INTEGER, -- id della tabella ruoli
            PRIMARY KEY (progetto_id, utente_id),
            FOREIGN KEY (progetto_id) REFERENCES progetti(id),
            FOREIGN KEY (utente_id) REFERENCES utenti(id),
            FOREIGN KEY (ruolo_id) REFERENCES ruoli(id)
        );
    ''')

    # Richieste ingresso ai progetti
    c.execute('''
        CREATE TABLE IF NOT EXISTS progetti_richieste (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utente_id INTEGER NOT NULL,
            progetto_id INTEGER NOT NULL,
            stato TEXT NOT NULL, -- pending, accepted, rejected
            data_request TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (utente_id) REFERENCES utenti(id),
            FOREIGN KEY (progetto_id) REFERENCES progetti(id)
        );
    ''')

    # Task (con assegnato_a e scadenza)
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titolo TEXT NOT NULL,
            descrizione TEXT,
            progetto_id INTEGER NOT NULL,
            parent_id INTEGER,
            autore_id INTEGER NOT NULL,
            stato TEXT NOT NULL,
            assegnato_a INTEGER,
            scadenza TEXT,
            data_creazione TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (progetto_id) REFERENCES progetti(id),
            FOREIGN KEY (parent_id) REFERENCES tasks(id),
            FOREIGN KEY (autore_id) REFERENCES utenti(id),
            FOREIGN KEY (assegnato_a) REFERENCES utenti(id)
        );
    ''')

    # Allegati (collegati a task)
    c.execute('''
        CREATE TABLE IF NOT EXISTS allegati (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            uploaded_by INTEGER,
            data_upload TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );
    ''')

    conn.commit()
    conn.close()
    print("Database QTasks inizializzato!")

if __name__ == "__main__":
    create_tables()

import os
import sqlite3

def create_tables():
    # Ottieni la directory assoluta del progetto (root)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "db", "qtasks.db")
    # Assicurati che la cartella esista
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(get_db_path())

    c = conn.cursor()

    # Utenti
    c.execute('''
        CREATE TABLE IF NOT EXISTS utenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            ruolo TEXT NOT NULL
        );
    ''')

    # Progetti
    c.execute('''
        CREATE TABLE IF NOT EXISTS progetti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            FOREIGN KEY (owner_id) REFERENCES utenti(id)
        );
    ''')

    # Task (con subtasks infiniti tramite parent_id)
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titolo TEXT NOT NULL,
            descrizione TEXT,
            progetto_id INTEGER NOT NULL,
            parent_id INTEGER,
            autore_id INTEGER NOT NULL,
            stato TEXT NOT NULL,
            data_creazione TEXT DEFAULT CURRENT_TIMESTAMP,
            data_scadenza TEXT,
            FOREIGN KEY (progetto_id) REFERENCES progetti(id),
            FOREIGN KEY (parent_id) REFERENCES tasks(id),
            FOREIGN KEY (autore_id) REFERENCES utenti(id)
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

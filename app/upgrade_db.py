import sqlite3
from app.config import get_db_path

db_path = get_db_path()
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Solo se questi campi non esistono già!
conn.execute("""
CREATE TABLE IF NOT EXISTS progetti_utenti (
    progetto_id INTEGER,
    utente_id INTEGER,
    PRIMARY KEY (progetto_id, utente_id),
    FOREIGN KEY (progetto_id) REFERENCES progetti(id),
    FOREIGN KEY (utente_id) REFERENCES utenti(id)
)
""")
conn.commit()


conn.commit()
conn.close()
print("Upgrade DB fatto!")

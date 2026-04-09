import sqlite3

# 👇 CAMBIA ESTO por la ruta real a tu .db
conn = sqlite3.connect("app.db")

conn.execute("ALTER TABLE datasets ADD COLUMN meta_json TEXT;")
conn.commit()
conn.close()

print("Columna meta_json añadida correctamente ✅")
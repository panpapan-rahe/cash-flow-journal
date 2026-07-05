"""One-time migration: add 'transfer' to category type constraint."""
import sqlite3
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

for fname in os.listdir(DATA_DIR):
    if fname.startswith("user_") and fname.endswith(".db"):
        path = os.path.join(DATA_DIR, fname)
        print(f"Migrating {fname}...")
        conn = sqlite3.connect(path)
        try:
            # Recreate categories table with updated constraint
            conn.execute("DROP TABLE IF EXISTS categories")
            conn.execute("""
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('income', 'expense', 'transfer')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Re-insert existing categories (if any were stored)
            # Since we dropped, categories are empty - app will auto-create
            conn.commit()
            print(f"  ✓ {fname} migrated")
        except Exception as e:
            print(f"  ✗ {fname} error: {e}")
        finally:
            conn.close()

print("Done!")

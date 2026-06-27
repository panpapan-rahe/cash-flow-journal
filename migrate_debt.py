"""Migration: add account_id & payment_account_id to existing debts table."""
import sqlite3
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

for fname in os.listdir(DATA_DIR):
    if fname.startswith("user_") and fname.endswith(".db"):
        path = os.path.join(DATA_DIR, fname)
        print(f"Migrating {fname}...")
        conn = sqlite3.connect(path)
        try:
            # Check if column exists
            cols = [row[1] for row in conn.execute("PRAGMA table_info(debts)").fetchall()]
            if 'account_id' not in cols:
                conn.execute("ALTER TABLE debts ADD COLUMN account_id INTEGER REFERENCES accounts(id)")
                conn.execute("ALTER TABLE debts ADD COLUMN payment_account_id INTEGER REFERENCES accounts(id)")
                conn.commit()
                print(f"  ✓ Columns added")
            else:
                print(f"  - Already migrated")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        finally:
            conn.close()

print("Done!")

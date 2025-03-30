import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('database.db')
c = conn.cursor()

# Delete the user with id = 1 (first user)
c.execute(
    f'CREATE TABLE categories(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    percentage REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);')

# Commit the changes and close the connection
conn.commit()
conn.close()

print("First user deleted successfully.")
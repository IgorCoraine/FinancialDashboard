import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('database.db')
c = conn.cursor()

# Delete the user with id = 1 (first user)
c.execute('DELETE FROM users WHERE id = 1')

# Commit the changes and close the connection
conn.commit()
conn.close()

print("First user deleted successfully.")
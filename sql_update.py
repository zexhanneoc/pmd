import sqlite3

conn = sqlite3.connect("rainfall.db")
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cursor.fetchall())

# Show sample data
cursor.execute("SELECT * FROM reports LIMIT 5")
print(cursor.fetchall())

cursor.execute("SELECT * FROM readings LIMIT 5")
print(cursor.fetchall())

conn.close()

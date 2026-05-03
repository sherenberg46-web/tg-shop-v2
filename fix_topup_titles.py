import sqlite3

conn = sqlite3.connect(r"C:\prodjects\tgshop\database\shop.db")
cur = conn.cursor()

updates = [
    ("PSN Turkey 250 TL", 89),
    ("PSN Turkey 500 TL", 90),
    ("PSN Turkey 750 TL", 91),
    ("PSN Turkey 1000 TL", 92),

    ("PSN Ukraine 400 UAH", 93),
    ("PSN Ukraine 600 UAH", 94),
    ("PSN Ukraine 1000 UAH", 95),

    ("PSN Poland 50 PLN", 96),
    ("PSN Poland 100 PLN", 97),
    ("PSN Poland 200 PLN", 98),

    ("PSN India 1000 INR", 99),
    ("PSN India 2000 INR", 100),
    ("PSN India 3000 INR", 101),
]

cur.executemany(
    "UPDATE products SET title = ? WHERE id = ?",
    updates
)

conn.commit()
conn.close()

print("Названия исправлены.")

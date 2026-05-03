import sqlite3

conn = sqlite3.connect(r"C:\prodjects\tgshop\database\shop.db")
cur = conn.cursor()

updates = [
    ("PSN Turkey 250 TL", "/images/topup250-tr.jpg"),
    ("PSN Turkey 500 TL", "/images/topup500-tr.jpg"),
    ("PSN Turkey 750 TL", "/images/topup750-tr.jpg"),
    ("PSN Turkey 1000 TL", "/images/topup1000-tr.jpg"),

    ("PSN Ukraine 400 UAH", "/images/topup-400uah.jpg"),
    ("PSN Ukraine 600 UAH", "/images/topup600-uah.jpg"),
    ("PSN Ukraine 1000 UAH", "/images/topup1000-uah.jpg"),

    ("PSN Poland 50 PLN", "/images/topup100-zl.jpg"),
    ("PSN Poland 100 PLN", "/images/topup100-zl.jpg"),
    ("PSN Poland 200 PLN", "/images/topup200-zl.jpg"),

    ("PSN India 1000 INR", "/images/topup1000-inr.jpg"),
    ("PSN India 2000 INR", "/images/topup2000-inr.jpg"),
    ("PSN India 3000 INR", "/images/topup3000-inr.jpg"),
]

for title, image in updates:
    cur.execute(
        "UPDATE products SET image_url = ? WHERE title = ?",
        (image, title)
    )

conn.commit()
conn.close()

print("Картинки для TOPUP обновлены.")

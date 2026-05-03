import sqlite3

conn = sqlite3.connect(r"C:\prodjects\tgshop\database\shop.db")
cur = conn.cursor()

products = [
    (3, "Пополнение PSN Турция 250 TL", "/images/topup-tr.jpg", 30, "topup"),
    (3, "Пополнение PSN Турция 500 TL", "/images/topup-tr.jpg", 55, "topup"),
    (3, "Пополнение PSN Турция 750 TL", "/images/topup-tr.jpg", 80, "topup"),
    (3, "Пополнение PSN Турция 1000 TL", "/images/topup-tr.jpg", 105, "topup"),

    (3, "Пополнение PSN Украина 400 UAH", "/images/topup-ua.jpg", 50, "topup"),
    (3, "Пополнение PSN Украина 600 UAH", "/images/topup-ua.jpg", 66, "topup"),
    (3, "Пополнение PSN Украина 1000 UAH", "/images/topup-ua.jpg", 110, "topup"),

    (3, "Пополнение PSN Польша 50 PLN", "/images/topup-pl.jpg", 56, "topup"),
    (3, "Пополнение PSN Польша 100 PLN", "/images/topup-pl.jpg", 113, "topup"),
    (3, "Пополнение PSN Польша 200 PLN", "/images/topup-pl.jpg", 225, "topup"),

    (3, "Пополнение PSN Индия 1000 INR", "/images/topup-in.jpg", 60, "topup"),
    (3, "Пополнение PSN Индия 2000 INR", "/images/topup-in.jpg", 120, "topup"),
    (3, "Пополнение PSN Индия 3000 INR", "/images/topup-in.jpg", 180, "topup"),
]

cur.executemany("""
INSERT INTO products
(category_id, title, image_url, price_uah, product_type)
VALUES (?, ?, ?, ?, ?)
""", products)

conn.commit()
conn.close()

print("TOPUP товары успешно добавлены.")

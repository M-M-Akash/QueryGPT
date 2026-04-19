import logging

from app.database.connection import get_connection

logger = logging.getLogger(__name__)


def seed_database() -> None:
    """Create tables and insert sample data if they don't already exist."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT,
                city TEXT,
                state TEXT,
                signup_date DATE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY,
                name TEXT,
                category TEXT,
                price REAL,
                stock_quantity INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                order_date DATE,
                total_amount REAL,
                status TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                item_id INTEGER PRIMARY KEY,
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                unit_price REAL,
                FOREIGN KEY (order_id) REFERENCES orders (order_id),
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            )
        """)

        if not cursor.execute("SELECT COUNT(*) FROM customers").fetchone()[0]:
            customers = [
                (1, "John Smith", "john@example.com", "New York", "NY", "2023-01-15"),
                (2, "Emma Johnson", "emma@example.com", "Los Angeles", "CA", "2023-02-20"),
                (3, "Michael Brown", "michael@example.com", "Chicago", "IL", "2023-03-10"),
                (4, "Sophia Davis", "sophia@example.com", "Houston", "TX", "2023-04-05"),
                (5, "William Wilson", "william@example.com", "Phoenix", "AZ", "2023-05-22"),
            ]
            cursor.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", customers)

            products = [
                (101, "Laptop", "Electronics", 999.99, 50),
                (102, "Smartphone", "Electronics", 699.99, 100),
                (103, "Coffee Maker", "Appliances", 79.99, 30),
                (104, "Headphones", "Electronics", 149.99, 75),
                (105, "Blender", "Appliances", 59.99, 25),
            ]
            cursor.executemany("INSERT INTO products VALUES (?,?,?,?,?)", products)

            orders = [
                (1001, 1, "2023-06-10", 1149.98, "Completed"),
                (1002, 2, "2023-06-15", 699.99, "Completed"),
                (1003, 3, "2023-06-20", 229.98, "Processing"),
                (1004, 4, "2023-06-25", 999.99, "Shipped"),
                (1005, 5, "2023-06-30", 139.98, "Pending"),
            ]
            cursor.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", orders)

            order_items = [
                (10001, 1001, 101, 1, 999.99),
                (10002, 1001, 103, 1, 79.99),
                (10003, 1002, 102, 1, 699.99),
                (10004, 1003, 104, 1, 149.99),
                (10005, 1003, 103, 1, 79.99),
                (10006, 1004, 101, 1, 999.99),
                (10007, 1005, 105, 1, 59.99),
                (10008, 1005, 103, 1, 79.99),
            ]
            cursor.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", order_items)

            logger.info("Sample data inserted successfully")

        conn.commit()
    logger.info("Database setup complete")

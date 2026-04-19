def get_sample_queries() -> list[dict]:
    """Return a set of sample SQL queries for RAG few-shot learning."""
    return [
        {
            "natural_language": "Find all customers from California",
            "sql": "SELECT * FROM customers WHERE state = 'CA'",
            "description": "Query to filter customers by state",
        },
        {
            "natural_language": "How many orders have been completed?",
            "sql": "SELECT COUNT(*) FROM orders WHERE status = 'Completed'",
            "description": "Count of orders with completed status",
        },
        {
            "natural_language": "Show me the total sales amount for each product",
            "sql": (
                "SELECT p.product_id, p.name, SUM(oi.quantity * oi.unit_price) as total_sales "
                "FROM products p JOIN order_items oi ON p.product_id = oi.product_id "
                "GROUP BY p.product_id, p.name"
            ),
            "description": "Total sales amount aggregated by product",
        },
        {
            "natural_language": "List the most recent orders",
            "sql": "SELECT * FROM orders ORDER BY order_date DESC LIMIT 5",
            "description": "Recent orders sorted by date",
        },
        {
            "natural_language": "Find customers who spent more than $1000",
            "sql": (
                "SELECT c.customer_id, c.name, SUM(o.total_amount) as total_spent "
                "FROM customers c JOIN orders o ON c.customer_id = o.customer_id "
                "GROUP BY c.customer_id, c.name HAVING total_spent > 1000"
            ),
            "description": "Customers with high spend",
        },
        {
            "natural_language": "What is the inventory value for each product category?",
            "sql": (
                "SELECT category, SUM(price * stock_quantity) as inventory_value "
                "FROM products GROUP BY category"
            ),
            "description": "Inventory value by product category",
        },
        {
            "natural_language": "Show me customers who purchased electronics",
            "sql": (
                "SELECT DISTINCT c.customer_id, c.name FROM customers c "
                "JOIN orders o ON c.customer_id = o.customer_id "
                "JOIN order_items oi ON o.order_id = oi.order_id "
                "JOIN products p ON oi.product_id = p.product_id "
                "WHERE p.category = 'Electronics'"
            ),
            "description": "Customers who bought products in electronics category",
        },
    ]

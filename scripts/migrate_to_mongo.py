import logging
from datetime import datetime, UTC

import pandas as pd
from sqlalchemy import create_engine, text
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError


POSTGRES_URL = "postgresql+psycopg2://retail_user:retail_pass@localhost:5432/retail_db"
MONGO_URL = "mongodb://localhost:27017"
MONGO_DB = "retail_nosql"

logging.basicConfig(
    filename="migration.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

pg_engine = create_engine(POSTGRES_URL)
mongo_client = MongoClient(MONGO_URL)
mongo_db = mongo_client[MONGO_DB]


def safe_float(value):
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def safe_int(value):
    if value is None or pd.isna(value):
        return 0
    return int(value)


def migrate_orders():
    print("Migrating orders_analytics...")

    query = """
        SELECT
            o.order_id,
            o.order_status,
            o.order_purchase_timestamp,
            o.order_delivered_customer_date,
            o.order_estimated_delivery_date,

            c.customer_id,
            c.customer_unique_id,
            c.customer_city,
            c.customer_state,

            COALESCE(items.item_count, 0) AS item_count,
            COALESCE(items.order_total, 0) AS order_total,
            COALESCE(items.freight_total, 0) AS freight_total,

            COALESCE(payments.payment_total, 0) AS payment_total,
            payments.payment_types,

            reviews.review_score,

            DATE_PART('day', o.order_delivered_customer_date - o.order_purchase_timestamp) AS delivery_days,
            DATE_PART('day', o.order_delivered_customer_date - o.order_estimated_delivery_date) AS delivery_delay_days

        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id

        LEFT JOIN (
            SELECT
                order_id,
                COUNT(*) AS item_count,
                SUM(price) AS order_total,
                SUM(freight_value) AS freight_total
            FROM order_items
            GROUP BY order_id
        ) items ON o.order_id = items.order_id

        LEFT JOIN (
            SELECT
                order_id,
                SUM(payment_value) AS payment_total,
                STRING_AGG(DISTINCT payment_type, ', ') AS payment_types
            FROM order_payments
            GROUP BY order_id
        ) payments ON o.order_id = payments.order_id

        LEFT JOIN (
            SELECT
                order_id,
                AVG(review_score) AS review_score
            FROM order_reviews
            GROUP BY order_id
        ) reviews ON o.order_id = reviews.order_id

        ORDER BY o.order_purchase_timestamp;
    """

    df = pd.read_sql(query, pg_engine)
    operations = []

    for _, row in df.iterrows():
        try:
            purchase_date = row["order_purchase_timestamp"]

            document = {
                "order_id": row["order_id"],
                "order_status": row["order_status"],
                "order_purchase_timestamp": purchase_date,
                "order_month": purchase_date.strftime("%Y-%m") if pd.notna(purchase_date) else None,

                "customer": {
                    "customer_id": row["customer_id"],
                    "customer_unique_id": row["customer_unique_id"],
                    "city": row["customer_city"],
                    "state": row["customer_state"]
                },

                "item_count": safe_int(row["item_count"]),
                "order_total": round(safe_float(row["order_total"]), 2),
                "freight_total": round(safe_float(row["freight_total"]), 2),
                "payment_total": round(safe_float(row["payment_total"]), 2),
                "payment_types": row["payment_types"] if pd.notna(row["payment_types"]) else None,
                "review_score": round(safe_float(row["review_score"]), 2) if pd.notna(row["review_score"]) else None,
                "delivery_days": safe_int(row["delivery_days"]) if pd.notna(row["delivery_days"]) else None,
                "delivery_delay_days": safe_int(row["delivery_delay_days"]) if pd.notna(row["delivery_delay_days"]) else None,
                "migrated_at": datetime.now(UTC)
            }

            operations.append(
                UpdateOne(
                    {"order_id": document["order_id"]},
                    {"$set": document},
                    upsert=True
                )
            )

            if len(operations) >= 2000:
                mongo_db.orders_analytics.bulk_write(operations, ordered=False)
                operations = []

        except Exception as e:
            logging.error(f"Error migrating order {row.get('order_id')}: {e}")

    if operations:
        mongo_db.orders_analytics.bulk_write(operations, ordered=False)

    mongo_db.orders_analytics.create_index("order_id", unique=True)
    mongo_db.orders_analytics.create_index("order_month")
    mongo_db.orders_analytics.create_index("customer.customer_unique_id")

    print(f"orders_analytics migrated: {mongo_db.orders_analytics.count_documents({})}")


def migrate_customers():
    print("Migrating customers_analytics...")

    pipeline = [
        {
            "$group": {
                "_id": "$customer.customer_unique_id",
                "customer_id": {"$first": "$customer.customer_id"},
                "city": {"$first": "$customer.city"},
                "state": {"$first": "$customer.state"},
                "total_orders": {"$sum": 1},
                "lifetime_value": {"$sum": "$order_total"},
                "average_order_value": {"$avg": "$order_total"},
                "last_order_date": {"$max": "$order_purchase_timestamp"}
            }
        }
    ]

    operations = []

    for doc in mongo_db.orders_analytics.aggregate(pipeline):
        if doc["_id"] is None:
            continue

        document = {
            "customer_unique_id": doc["_id"],
            "customer_id": doc.get("customer_id"),
            "city": doc.get("city"),
            "state": doc.get("state"),
            "total_orders": safe_int(doc.get("total_orders")),
            "lifetime_value": round(safe_float(doc.get("lifetime_value")), 2),
            "average_order_value": round(safe_float(doc.get("average_order_value")), 2),
            "last_order_date": doc.get("last_order_date"),
            "migrated_at": datetime.now(UTC)
        }

        operations.append(
            UpdateOne(
                {"customer_unique_id": document["customer_unique_id"]},
                {"$set": document},
                upsert=True
            )
        )

        if len(operations) >= 2000:
            mongo_db.customers_analytics.bulk_write(operations, ordered=False)
            operations = []

    if operations:
        mongo_db.customers_analytics.bulk_write(operations, ordered=False)

    mongo_db.customers_analytics.create_index("customer_unique_id", unique=True)
    print(f"customers_analytics migrated: {mongo_db.customers_analytics.count_documents({})}")


def migrate_products():
    print("Migrating products_analytics...")

    query = """
        SELECT
            p.product_id,
            COALESCE(ct.product_category_name_english, p.product_category_name) AS category,
            COUNT(oi.order_item_id) AS units_sold,
            SUM(oi.price) AS product_revenue,
            SUM(oi.freight_value) AS freight_revenue,
            COUNT(DISTINCT oi.order_id) AS order_count
        FROM products p
        JOIN order_items oi ON p.product_id = oi.product_id
        LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
        GROUP BY p.product_id, category;
    """

    df = pd.read_sql(query, pg_engine)
    operations = []

    for _, row in df.iterrows():
        try:
            document = {
                "product_id": row["product_id"],
                "category": row["category"],
                "units_sold": safe_int(row["units_sold"]),
                "product_revenue": round(safe_float(row["product_revenue"]), 2),
                "freight_revenue": round(safe_float(row["freight_revenue"]), 2),
                "order_count": safe_int(row["order_count"]),
                "migrated_at": datetime.now(UTC)
            }

            operations.append(
                UpdateOne(
                    {"product_id": document["product_id"]},
                    {"$set": document},
                    upsert=True
                )
            )

            if len(operations) >= 2000:
                mongo_db.products_analytics.bulk_write(operations, ordered=False)
                operations = []

        except Exception as e:
            logging.error(f"Error migrating product {row.get('product_id')}: {e}")

    if operations:
        mongo_db.products_analytics.bulk_write(operations, ordered=False)

    mongo_db.products_analytics.create_index("product_id", unique=True)
    mongo_db.products_analytics.create_index("category")

    print(f"products_analytics migrated: {mongo_db.products_analytics.count_documents({})}")


def main():
    print("Starting PostgreSQL to MongoDB migration...")

    try:
        mongo_client.admin.command("ping")
        print("MongoDB connection OK.")

        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("PostgreSQL connection OK.")

        migrate_orders()
        migrate_customers()
        migrate_products()

        print("Migration completed successfully.")

    except PyMongoError as e:
        logging.error(f"MongoDB error: {e}")
        print("MongoDB error. Check migration.log")
    except Exception as e:
        logging.error(f"Migration error: {e}")
        print("Migration error. Check migration.log")


if __name__ == "__main__":
    main()

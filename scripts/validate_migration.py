import hashlib
from decimal import Decimal

from sqlalchemy import create_engine, text
from pymongo import MongoClient


POSTGRES_URL = "postgresql+psycopg2://retail_user:retail_pass@localhost:5432/retail_db"
MONGO_URL = "mongodb://localhost:27017"
MONGO_DB = "retail_nosql"

pg_engine = create_engine(POSTGRES_URL)
mongo_client = MongoClient(MONGO_URL)
mongo_db = mongo_client[MONGO_DB]


def safe_float(value):
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def print_result(name, passed, source_value, target_value):
    status = "PASS" if passed else "FAIL"
    print(f"{name}: {status}")
    print(f"  PostgreSQL: {source_value}")
    print(f"  MongoDB:    {target_value}")
    print()


def hash_value(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def validate_counts():
    print("1. Record count validation")
    print("--------------------------")

    checks = [
        ("orders", "orders_analytics", "SELECT COUNT(*) FROM orders"),
        ("products", "products_analytics", "SELECT COUNT(*) FROM products"),
    ]

    with pg_engine.connect() as conn:
        for source_name, mongo_collection, sql_query in checks:
            pg_count = conn.execute(text(sql_query)).scalar()
            mongo_count = mongo_db[mongo_collection].count_documents({})
            print_result(
                f"{source_name} count",
                pg_count == mongo_count,
                pg_count,
                mongo_count
            )

        pg_customers = conn.execute(text("SELECT COUNT(DISTINCT customer_unique_id) FROM customers")).scalar()
        mongo_customers = mongo_db.customers_analytics.count_documents({})
        print_result(
            "unique customers count",
            pg_customers == mongo_customers,
            pg_customers,
            mongo_customers
        )


def validate_revenue_totals():
    print("2. Revenue total validation")
    print("---------------------------")

    with pg_engine.connect() as conn:
        pg_order_total = conn.execute(text("SELECT ROUND(SUM(price), 2) FROM order_items")).scalar()
        pg_freight_total = conn.execute(text("SELECT ROUND(SUM(freight_value), 2) FROM order_items")).scalar()
        pg_payment_total = conn.execute(text("SELECT ROUND(SUM(payment_value), 2) FROM order_payments")).scalar()

    mongo_order_total = list(mongo_db.orders_analytics.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$order_total"}}}
    ]))[0]["total"]

    mongo_freight_total = list(mongo_db.orders_analytics.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$freight_total"}}}
    ]))[0]["total"]

    mongo_payment_total = list(mongo_db.orders_analytics.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$payment_total"}}}
    ]))[0]["total"]

    print_result(
        "order revenue total",
        round(safe_float(pg_order_total), 2) == round(safe_float(mongo_order_total), 2),
        round(safe_float(pg_order_total), 2),
        round(safe_float(mongo_order_total), 2)
    )

    print_result(
        "freight total",
        round(safe_float(pg_freight_total), 2) == round(safe_float(mongo_freight_total), 2),
        round(safe_float(pg_freight_total), 2),
        round(safe_float(mongo_freight_total), 2)
    )

    print_result(
        "payment total",
        round(safe_float(pg_payment_total), 2) == round(safe_float(mongo_payment_total), 2),
        round(safe_float(pg_payment_total), 2),
        round(safe_float(mongo_payment_total), 2)
    )


def validate_checksum():
    print("3. Checksum validation")
    print("----------------------")

    with pg_engine.connect() as conn:
        pg_order_ids = conn.execute(text("""
            SELECT STRING_AGG(order_id, ',' ORDER BY order_id)
            FROM orders
        """)).scalar()

    mongo_order_ids = ",".join(
        doc["order_id"]
        for doc in mongo_db.orders_analytics.find({}, {"order_id": 1, "_id": 0}).sort("order_id", 1)
    )

    pg_hash = hash_value(pg_order_ids)
    mongo_hash = hash_value(mongo_order_ids)

    print_result(
        "order_id checksum",
        pg_hash == mongo_hash,
        pg_hash,
        mongo_hash
    )


def validate_spot_check():
    print("4. Spot-check validation")
    print("------------------------")

    with pg_engine.connect() as conn:
        row = conn.execute(text("""
            SELECT
                o.order_id,
                COUNT(oi.order_item_id) AS item_count,
                ROUND(SUM(oi.price), 2) AS order_total,
                ROUND(SUM(oi.freight_value), 2) AS freight_total
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            GROUP BY o.order_id
            ORDER BY o.order_id
            LIMIT 1
        """)).mappings().first()

    mongo_doc = mongo_db.orders_analytics.find_one({"order_id": row["order_id"]})

    pg_values = {
        "order_id": row["order_id"],
        "item_count": int(row["item_count"]),
        "order_total": round(safe_float(row["order_total"]), 2),
        "freight_total": round(safe_float(row["freight_total"]), 2)
    }

    mongo_values = {
        "order_id": mongo_doc["order_id"],
        "item_count": mongo_doc["item_count"],
        "order_total": round(safe_float(mongo_doc["order_total"]), 2),
        "freight_total": round(safe_float(mongo_doc["freight_total"]), 2)
    }

    print_result(
        f"spot-check order {row['order_id']}",
        pg_values == mongo_values,
        pg_values,
        mongo_values
    )


def main():
    print()
    print("DATA VALIDATION REPORT")
    print("======================")
    print()

    validate_counts()
    validate_revenue_totals()
    validate_checksum()
    validate_spot_check()

    print("Validation completed.")


if __name__ == "__main__":
    main()

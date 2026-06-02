import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path

DB_URL = "postgresql+psycopg2://retail_user:retail_pass@localhost:5432/retail_db"
RAW_DIR = Path("data/raw")

engine = create_engine(DB_URL)


def read_csv(filename):
    path = RAW_DIR / filename
    print(f"Reading {path}")
    return pd.read_csv(path)


def clean_datetime_columns(df, columns):
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def load_table(df, table_name):
    print(f"Loading {table_name}: {len(df)} rows")
    df.to_sql(table_name, engine, if_exists="append", index=False, method="multi", chunksize=1000)


def main():
    print("Starting PostgreSQL data load...")

    # Clear old data so the loader can be safely re-run.
    with engine.begin() as conn:
        conn.execute(text("""
            TRUNCATE TABLE
                order_reviews,
                order_payments,
                order_items,
                orders,
                products,
                sellers,
                customers,
                category_translation
            CASCADE;
        """))

    customers = read_csv("olist_customers_dataset.csv")
    sellers = read_csv("olist_sellers_dataset.csv")
    category_translation = read_csv("product_category_name_translation.csv")
    products = read_csv("olist_products_dataset.csv")
    orders = read_csv("olist_orders_dataset.csv")
    order_items = read_csv("olist_order_items_dataset.csv")
    order_payments = read_csv("olist_order_payments_dataset.csv")
    order_reviews = read_csv("olist_order_reviews_dataset.csv")

    # Clean date columns
    orders = clean_datetime_columns(orders, [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date"
    ])

    order_items = clean_datetime_columns(order_items, ["shipping_limit_date"])

    order_reviews = clean_datetime_columns(order_reviews, [
        "review_creation_date",
        "review_answer_timestamp"
    ])

    # Some products may have missing category names. Missing values are allowed.
    valid_categories = set(category_translation["product_category_name"].dropna())
    products.loc[
        ~products["product_category_name"].isin(valid_categories),
        "product_category_name"
    ] = None

    # Load parent tables first, then child tables.
    load_table(customers, "customers")
    load_table(sellers, "sellers")
    load_table(category_translation, "category_translation")
    load_table(products, "products")
    load_table(orders, "orders")
    load_table(order_items, "order_items")
    load_table(order_payments, "order_payments")
    load_table(order_reviews, "order_reviews")

    print("\nRecord counts:")
    with engine.connect() as conn:
        for table in [
            "customers",
            "sellers",
            "category_translation",
            "products",
            "orders",
            "order_items",
            "order_payments",
            "order_reviews"
        ]:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"{table}: {count}")

    print("\nPostgreSQL data load completed successfully.")


if __name__ == "__main__":
    main()

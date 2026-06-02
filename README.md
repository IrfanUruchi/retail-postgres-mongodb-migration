# Retail PostgreSQL to MongoDB Migration

A full relational-to-NoSQL migration project using PostgreSQL, MongoDB, Python, Docker, and Streamlit.

This project uses the Olist Brazilian E-Commerce dataset to demonstrate how data can be moved from a relational database into a NoSQL database while changing the structure for analytics use. The goal is not only to copy data from PostgreSQL to MongoDB, but to redesign it into MongoDB collections that are easier to query, validate, and visualize.

## Project Overview

The project follows this pipeline:

```text
Olist CSV files
        ↓
PostgreSQL relational database
        ↓
Python migration script
        ↓
MongoDB analytics collections
        ↓
Validation script
        ↓
Streamlit dashboard
```

PostgreSQL is used as the relational source database. MongoDB is used as the NoSQL target database. The dashboard reads only from MongoDB after the migration is complete.

## Main Features

* Relational database design in PostgreSQL
* Primary keys, foreign keys, NOT NULL fields, UNIQUE constraint, and CHECK constraints
* CSV loading from the Olist dataset into PostgreSQL
* Programmatic migration from PostgreSQL to MongoDB
* Denormalized MongoDB analytics collections
* Derived fields created during migration
* Idempotent migration using MongoDB upserts
* MongoDB indexes for faster updates and queries
* Validation between PostgreSQL and MongoDB
* Streamlit dashboard reading only from MongoDB
* Order inspection and migration quality checks

## Technologies Used

* PostgreSQL 16
* MongoDB 7
* Python 3
* Pandas
* SQLAlchemy
* psycopg2
* PyMongo
* Streamlit
* Plotly
* Docker Compose

## Dataset

This project uses the **Brazilian E-Commerce Public Dataset by Olist**.

The dataset contains real e-commerce data such as customers, orders, order items, payments, reviews, products, sellers, geolocation data, and product category translations.

The CSV files are not included directly in this repository. To run the project, download the dataset from Kaggle and place the CSV files inside:

```text
data/raw/
```

Expected files:

```text
olist_customers_dataset.csv
olist_geolocation_dataset.csv
olist_order_items_dataset.csv
olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv
olist_orders_dataset.csv
olist_products_dataset.csv
olist_sellers_dataset.csv
product_category_name_translation.csv
```

A small README file is included inside `data/raw/` with the same instructions.

## Project Structure

```text
retail-postgres-mongodb-migration/
├── dashboard/
│   └── app.py
├── data/
│   └── raw/
│       └── README.md
├── scripts/
│   ├── load_postgres.py
│   ├── migrate_to_mongo.py
│   └── validate_migration.py
├── sql/
│   └── schema.sql
├── docker-compose.yml
├── requirements.txt
├── README.md
└── report.md
```

## PostgreSQL Relational Model

The PostgreSQL database contains the main relational structure of the dataset.

Tables used:

```text
customers
sellers
category_translation
products
orders
order_items
order_payments
order_reviews
```

The schema includes:

```text
Primary keys
Foreign keys
NOT NULL fields
UNIQUE constraint
CHECK constraints
```

Examples of relationships:

```text
customers → orders
orders → order_items
orders → order_payments
orders → order_reviews
order_items → products
order_items → sellers
products → category_translation
```

PostgreSQL is used first because the original dataset is naturally relational and spread across multiple CSV files connected by IDs.

## MongoDB NoSQL Model

The MongoDB side is not a direct copy of the PostgreSQL tables. Instead, the data is transformed into analytics-oriented collections.

MongoDB collections created:

```text
orders_analytics
customers_analytics
products_analytics
```

### orders_analytics

Stores order-level data with customer details and calculated fields.

Example calculated fields:

```text
order_total
freight_total
payment_total
item_count
delivery_days
delivery_delay_days
```

### customers_analytics

Stores customer-level summary data.

Example calculated fields:

```text
total_orders
lifetime_value
average_order_value
last_order_date
```

### products_analytics

Stores product-level summary data.

Example calculated fields:

```text
units_sold
product_revenue
freight_revenue
order_count
```

This structure is more suitable for MongoDB because the dashboard can read prepared documents instead of joining multiple tables every time.

## How to Run the Project

### 1. Clone the repository

```bash
git clone https://github.com/IrfanUruchi/retail-postgres-mongodb-migration.git
cd retail-postgres-mongodb-migration
```

### 2. Download the dataset

Download the Brazilian E-Commerce Public Dataset by Olist from Kaggle.

Place the CSV files inside:

```text
data/raw/
```

The project expects all 9 CSV files to be present before loading data into PostgreSQL.

### 3. Start PostgreSQL and MongoDB

Make sure Docker Desktop is running.

Then start the containers:

```bash
docker compose up -d
```

Check that the containers are running:

```bash
docker ps
```

Expected containers:

```text
nosql_postgres
nosql_mongo
```

### 4. Create and activate Python environment

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 5. Load CSV data into PostgreSQL

```bash
python scripts/load_postgres.py
```

Expected PostgreSQL record counts:

```text
customers: 99441
sellers: 3095
category_translation: 71
products: 32951
orders: 99441
order_items: 112650
order_payments: 103886
order_reviews: 99224
```

### 6. Migrate PostgreSQL data to MongoDB

```bash
python scripts/migrate_to_mongo.py
```

Expected MongoDB document counts:

```text
orders_analytics: 99441
customers_analytics: 96096
products_analytics: 32951
```

The migration uses MongoDB upserts, so running the migration again updates existing documents instead of creating duplicates.

### 7. Validate the migration

```bash
python scripts/validate_migration.py
```

The validation script checks:

```text
Record counts
Revenue totals
Freight totals
Payment totals
order_id checksum
Spot-check order comparison
```

Expected result:

```text
orders count: PASS
products count: PASS
unique customers count: PASS
order revenue total: PASS
freight total: PASS
payment total: PASS
order_id checksum: PASS
spot-check order comparison: PASS
```

### 8. Run the dashboard

```bash
streamlit run dashboard/app.py
```

Open the dashboard at:

```text
http://localhost:8501
```

## Dashboard

The dashboard reads only from MongoDB. PostgreSQL is not used by the dashboard.

Dashboard tabs:

```text
Executive
Revenue Quality
Product Portfolio
Customer Value
Delivery Risk
Order Inspector
Migration Quality
```

### Executive

Shows the main project metrics such as health score, orders, revenue, average order value, late delivery rate, non-delivered orders, top revenue state, best revenue month, and top category.

### Revenue Quality

Shows monthly revenue, payment totals, freight totals, payment gaps, freight share, revenue growth, and payment type distribution.

### Product Portfolio

Shows top product categories, product revenue, product units sold, and category Pareto analysis.

### Customer Value

Shows top customers by lifetime value and customer value by state.

### Delivery Risk

Shows delivery delay distribution, states with higher late delivery rate, late delivery rate by month, and highest delay orders.

### Order Inspector

Allows checking one MongoDB order document by `order_id`.

### Migration Quality

Shows MongoDB document counts, financial totals, indexes, and sample migrated data.

## Validation Result

The final validation confirmed that the migrated MongoDB data matches the PostgreSQL source data for the main checks used in this project.

Validation summary:

```text
orders count: PASS
products count: PASS
unique customers count: PASS
order revenue total: PASS
freight total: PASS
payment total: PASS
order_id checksum: PASS
spot-check order comparison: PASS
```

This confirms that the migration did not lose records and that the main financial values match between PostgreSQL and MongoDB.

## Notes

The dashboard is read-only for the migrated MongoDB analytics collections. This keeps the MongoDB data consistent with the PostgreSQL source and keeps validation meaningful.

The dataset CSV files are not included in this repository. The README explains how to download the dataset and where to place the files before running the project.

## Repository

GitHub repository:

```text
https://github.com/IrfanUruchi/retail-postgres-mongodb-migration
```

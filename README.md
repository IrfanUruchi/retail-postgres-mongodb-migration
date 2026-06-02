# Retail Data Migration from PostgreSQL to MongoDB

This repository contains a NoSQL database project focused on migrating retail e-commerce data from a relational database into a document-oriented NoSQL database.

The project uses the **Olist Brazilian E-Commerce dataset** as the source dataset. The data is first loaded into **PostgreSQL** using a relational schema with tables, primary keys, foreign keys, and constraints. After that, the data is migrated into **MongoDB** collections that are designed for analysis and dashboard usage.

The purpose of the project is not only to copy data from one database to another, but also to change the structure of the data so it is more suitable for NoSQL usage.

## Project Objective

The main objective of this project is to demonstrate a full relational-to-NoSQL migration process.

The project includes:

* loading CSV files into PostgreSQL
* creating a relational schema with relationships and constraints
* migrating relational data into MongoDB documents
* creating calculated fields during migration
* validating MongoDB data against PostgreSQL data
* building a dashboard that reads only from MongoDB

The final result is a MongoDB database that can be used for filtering, analysis, order inspection, and visualization.

## Project Pipeline

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

## Technologies Used

| Technology     | Purpose                                    |
| -------------- | ------------------------------------------ |
| PostgreSQL 16  | Relational source database                 |
| MongoDB 7      | NoSQL target database                      |
| Python 3       | Data loading, migration, and validation    |
| Pandas         | CSV reading and data processing            |
| SQLAlchemy     | PostgreSQL connection and loading          |
| psycopg2       | PostgreSQL driver                          |
| PyMongo        | MongoDB connection and document operations |
| Streamlit      | Interactive dashboard                      |
| Plotly         | Dashboard visualizations                   |
| Docker Compose | Local database environment                 |

## Dataset

This project uses the **Brazilian E-Commerce Public Dataset by Olist**.

The dataset contains e-commerce data such as:

* customers
* orders
* order items
* payments
* reviews
* products
* sellers
* geolocation data
* product category translations

The dataset CSV files are not included directly in this repository. To run the project, download the dataset from Kaggle and place the CSV files inside:

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

A separate `README.md` file is included inside `data/raw/` with the same dataset instructions.

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

## Database Setup

The project uses Docker Compose to start PostgreSQL and MongoDB locally.

Start the database containers:

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

On macOS, Docker Desktop must be running before using Docker commands.

## PostgreSQL Relational Model

PostgreSQL is used as the relational source database.

The database contains these tables:

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

The relational schema includes:

* primary keys
* foreign keys
* `NOT NULL` fields
* `UNIQUE` constraint
* `CHECK` constraints

Main relationships:

```text
customers → orders
orders → order_items
orders → order_payments
orders → order_reviews
order_items → products
order_items → sellers
products → category_translation
```

PostgreSQL is used first because the original Olist dataset is naturally relational and stored across multiple CSV files connected by IDs.

The schema file is located in:

```text
sql/schema.sql
```

## Loading Data into PostgreSQL

After placing the dataset CSV files inside `data/raw/`, run:

```bash
python scripts/load_postgres.py
```

The script reads the CSV files, prepares the data, and loads it into PostgreSQL tables in the correct order so that foreign key constraints do not fail.

Expected record counts after loading:

| Table                | Records |
| -------------------- | ------: |
| customers            |   99441 |
| sellers              |    3095 |
| category_translation |      71 |
| products             |   32951 |
| orders               |   99441 |
| order_items          |  112650 |
| order_payments       |  103886 |
| order_reviews        |   99224 |

## MongoDB NoSQL Model

MongoDB is used as the NoSQL target database.

Instead of copying every PostgreSQL table into a separate MongoDB collection, the data is transformed into analytics-oriented collections.

MongoDB collections created:

```text
orders_analytics
customers_analytics
products_analytics
```

This design is used because MongoDB works well with document-based structures. The migrated collections are prepared for reading and analysis instead of requiring joins across many tables.

## MongoDB Collections

### `orders_analytics`

Stores order-level data, customer information, payment data, review score, and calculated fields.

Example calculated fields:

```text
order_total
freight_total
payment_total
item_count
delivery_days
delivery_delay_days
order_month
```

### `customers_analytics`

Stores summarized customer data.

Example fields:

```text
total_orders
lifetime_value
average_order_value
last_order_date
```

### `products_analytics`

Stores summarized product data.

Example fields:

```text
units_sold
product_revenue
freight_revenue
order_count
category
```

## Migration Process

The migration script is located in:

```text
scripts/migrate_to_mongo.py
```

Run the migration with:

```bash
python scripts/migrate_to_mongo.py
```

The script connects to PostgreSQL, reads the relational data, calculates new fields, and writes the transformed data into MongoDB.

Expected MongoDB document counts:

| Collection          | Documents |
| ------------------- | --------: |
| orders_analytics    |     99441 |
| customers_analytics |     96096 |
| products_analytics  |     32951 |

The migration uses MongoDB upsert operations. This means that if the migration script is run again, existing documents are updated instead of duplicated.

## Derived Fields

During migration, several calculated fields are created to make the MongoDB collections more useful for analysis.

| Field                 | Description                                                   |
| --------------------- | ------------------------------------------------------------- |
| `order_total`         | Total item price for an order                                 |
| `freight_total`       | Total freight value for an order                              |
| `payment_total`       | Total payment value for an order                              |
| `item_count`          | Number of items in an order                                   |
| `delivery_days`       | Number of days between purchase and delivery                  |
| `delivery_delay_days` | Difference between delivered date and estimated delivery date |
| `lifetime_value`      | Total value generated by a customer                           |
| `average_order_value` | Average order value for a customer                            |
| `product_revenue`     | Total revenue generated by a product                          |
| `units_sold`          | Total number of product units sold                            |

## MongoDB Indexes

Indexes are created to support faster lookup, migration updates, and dashboard queries.

Main indexes include:

```text
orders_analytics.order_id
orders_analytics.order_month
orders_analytics.customer.customer_unique_id
customers_analytics.customer_unique_id
products_analytics.product_id
products_analytics.category
```

## Data Validation

The validation script is located in:

```text
scripts/validate_migration.py
```

Run validation with:

```bash
python scripts/validate_migration.py
```

The validation compares PostgreSQL and MongoDB using:

* record counts
* revenue totals
* freight totals
* payment totals
* checksum validation
* spot-check comparison for one order

Expected validation result:

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

The validation step confirms that the migration did not lose records and that the main financial totals match between PostgreSQL and MongoDB.

## Dashboard

The dashboard is built using Streamlit and Plotly.

Run the dashboard with:

```bash
streamlit run dashboard/app.py
```

Open it at:

```text
http://localhost:8501
```

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

## Dashboard Features

### Executive

Shows the main overview of the migrated data, including revenue, order count, average order value, late delivery rate, non-delivered orders, top revenue state, best revenue month, and top product category.

### Revenue Quality

Shows monthly revenue, payment totals, freight totals, payment gaps, freight share, and payment type distribution.

### Product Portfolio

Shows top product categories, product revenue, category Pareto analysis, and product-level performance.

### Customer Value

Shows highest value customers and customer value by state using the `customers_analytics` collection.

### Delivery Risk

Shows delivery delay distribution, late delivery rate by month, states with higher delivery risk, and orders with the highest delays.

### Order Inspector

Allows searching for a specific order by `order_id` and inspecting the full MongoDB document.

### Migration Quality

Shows document counts, financial totals, MongoDB indexes, and a preview of migrated data.

## How to Run the Full Project

### 1. Clone the repository

```bash
git clone https://github.com/IrfanUruchi/retail-postgres-mongodb-migration.git
cd retail-postgres-mongodb-migration
```

### 2. Download the dataset

Download the Olist Brazilian E-Commerce dataset from Kaggle and place the CSV files inside:

```text
data/raw/
```

### 3. Start PostgreSQL and MongoDB

```bash
docker compose up -d
```

### 4. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Load PostgreSQL data

```bash
python scripts/load_postgres.py
```

### 7. Migrate data to MongoDB

```bash
python scripts/migrate_to_mongo.py
```

### 8. Validate migration

```bash
python scripts/validate_migration.py
```

### 9. Run dashboard

```bash
streamlit run dashboard/app.py
```

## Useful Commands

Check PostgreSQL tables:

```bash
docker exec -it nosql_postgres psql -U retail_user -d retail_db -c "\dt"
```

Check MongoDB collections:

```bash
docker exec -it nosql_mongo mongosh retail_nosql --eval "show collections"
```

Stop Docker containers:

```bash
docker compose down
```

Restart Docker containers:

```bash
docker compose up -d
```

## Troubleshooting

### Docker is not running

If Docker commands fail with a Docker API connection error, start Docker Desktop first and then run:

```bash
docker compose up -d
```

### Dataset files are missing

If the loading script fails because CSV files are missing, check that the Olist CSV files are inside:

```text
data/raw/
```

### Validation fails

If validation fails, rerun the full pipeline:

```bash
python scripts/load_postgres.py
python scripts/migrate_to_mongo.py
python scripts/validate_migration.py
```

### Dashboard shows no data

If the dashboard opens but no data appears, make sure the migration script has been executed:

```bash
python scripts/migrate_to_mongo.py
```

Then restart the dashboard.

## Notes

The dashboard is read-only for the migrated MongoDB collections. This keeps the MongoDB data consistent with the PostgreSQL source and keeps the validation results meaningful.

The dataset CSV files are not included in this repository. They must be downloaded separately and placed inside `data/raw/`.

The project was created as a complete migration pipeline, including database design, data population, NoSQL modeling, migration, validation, and visualization.

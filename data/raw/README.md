# Dataset Folder

This folder is used for the Olist Brazilian E-Commerce dataset CSV files.

The CSV files are not included in this repository to keep the project lighter and avoid redistributing the dataset directly.

Dataset used:
Brazilian E-Commerce Public Dataset by Olist

Download it from Kaggle, then place these files inside this folder:

- olist_customers_dataset.csv
- olist_geolocation_dataset.csv
- olist_order_items_dataset.csv
- olist_order_payments_dataset.csv
- olist_order_reviews_dataset.csv
- olist_orders_dataset.csv
- olist_products_dataset.csv
- olist_sellers_dataset.csv
- product_category_name_translation.csv

After placing the files here, run:

python scripts/load_postgres.py

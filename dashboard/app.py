from datetime import datetime, timedelta
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pymongo import MongoClient


MONGO_URL = "mongodb://localhost:27017"
MONGO_DB = "retail_nosql"

st.set_page_config(
    page_title="Retail Operations Dashboard",
    page_icon="🛒",
    layout="wide"
)

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1440px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        h1 {
            font-weight: 850 !important;
            letter-spacing: -0.05em;
        }

        h2, h3 {
            letter-spacing: -0.03em;
        }

        .muted {
            color: #6e6e73;
            font-size: 0.96rem;
        }

        .kpi-card {
            background: #ffffff;
            border: 1px solid #e5e5ea;
            border-radius: 22px;
            padding: 20px 22px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.05);
            min-height: 126px;
        }

        .kpi-label {
            color: #6e6e73;
            font-size: 0.86rem;
            font-weight: 650;
            margin-bottom: 0.4rem;
        }

        .kpi-value {
            color: #1d1d1f;
            font-size: 1.7rem;
            font-weight: 850;
            letter-spacing: -0.04em;
        }

        .kpi-note {
            color: #86868b;
            font-size: 0.84rem;
            margin-top: 0.4rem;
        }

        .insight-card {
            background: linear-gradient(180deg, #ffffff 0%, #fbfbfd 100%);
            border: 1px solid #e5e5ea;
            border-radius: 22px;
            padding: 20px 22px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.05);
            min-height: 136px;
        }

        .insight-title {
            color: #6e6e73;
            font-size: 0.86rem;
            font-weight: 650;
            margin-bottom: 0.45rem;
        }

        .insight-value {
            color: #1d1d1f;
            font-size: 1.33rem;
            font-weight: 850;
            letter-spacing: -0.035em;
        }

        .insight-text {
            color: #6e6e73;
            font-size: 0.92rem;
            margin-top: 0.45rem;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e5ea;
            border-radius: 20px;
            padding: 18px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.04);
        }

        div[data-testid="stTabs"] button {
            font-weight: 650;
        }
    </style>
    """,
    unsafe_allow_html=True
)


@st.cache_resource
def get_db():
    return MongoClient(MONGO_URL)[MONGO_DB]


db = get_db()

PAYMENT_LABELS = {
    "credit_card": "Credit card",
    "debit_card": "Debit card",
    "voucher": "Voucher",
    "boleto": "Boleto payment slip",
    "not_defined": "Not defined"
}


def payment_label(value):
    return PAYMENT_LABELS.get(value, value)


def money(value):
    return f"{float(value or 0):,.2f}"


def short_money(value):
    value = float(value or 0)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.2f}"


def kpi_card(label, value, note):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def insight_card(title, value, text):
    st.markdown(
        f"""
        <div class="insight-card">
            <div class="insight-title">{title}</div>
            <div class="insight-value">{value}</div>
            <div class="insight-text">{text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def chart_style(fig, height=430):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=20, r=20, t=55, b=35),
        hovermode="x unified",
        font=dict(size=13),
    )
    return fig


@st.cache_data(show_spinner=False)
def get_filter_data():
    date_info = list(db.orders_analytics.aggregate([
        {
            "$group": {
                "_id": None,
                "min_date": {"$min": "$order_purchase_timestamp"},
                "max_date": {"$max": "$order_purchase_timestamp"},
                "min_total": {"$min": "$order_total"},
                "max_total": {"$max": "$order_total"}
            }
        }
    ]))[0]

    states = sorted([x for x in db.orders_analytics.distinct("customer.state") if x])
    statuses = sorted([x for x in db.orders_analytics.distinct("order_status") if x])

    raw_payments = db.orders_analytics.distinct("payment_types")
    payments = sorted({
        item.strip()
        for value in raw_payments
        if value
        for item in str(value).split(",")
        if item.strip()
    })

    return date_info, states, statuses, payments


def build_match(start_date, end_date, states, statuses, payments, min_total, max_total):
    query = {
        "order_purchase_timestamp": {
            "$gte": datetime.combine(start_date, datetime.min.time()),
            "$lt": datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        },
        "order_total": {
            "$gte": float(min_total),
            "$lte": float(max_total)
        }
    }

    if states:
        query["customer.state"] = {"$in": states}

    if statuses:
        query["order_status"] = {"$in": statuses}

    if payments:
        query["payment_types"] = {
            "$regex": "|".join(re.escape(p) for p in payments),
            "$options": "i"
        }

    return query


def order_agg(pipeline):
    return list(db.orders_analytics.aggregate(pipeline))


def product_agg(pipeline):
    return list(db.products_analytics.aggregate(pipeline))


def customer_agg(pipeline):
    return list(db.customers_analytics.aggregate(pipeline))


def df_from(data):
    return pd.DataFrame(data)


def health_score(late_rate, problem_count, orders_count, avg_review):
    score = 100
    score -= min(late_rate * 1.2, 30)
    if orders_count:
        score -= min((problem_count / orders_count) * 100 * 2, 25)
    if avg_review:
        score -= max(0, (5 - avg_review) * 8)
    return max(0, min(100, round(score, 1)))


left, right = st.columns([0.75, 0.25])

with left:
    st.title("Retail Operations Dashboard")
    st.markdown(
        "<div class='muted'>MongoDB analytics layer built after migrating and transforming PostgreSQL retail data.</div>",
        unsafe_allow_html=True
    )

with right:
    st.write("")
    if st.button("Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


date_info, states, statuses, payment_types = get_filter_data()

with st.expander("Filters", expanded=False):
    f1, f2, f3 = st.columns(3)

    with f1:
        date_range = st.date_input(
            "Date range",
            value=(date_info["min_date"].date(), date_info["max_date"].date()),
            min_value=date_info["min_date"].date(),
            max_value=date_info["max_date"].date()
        )

    with f2:
        selected_states = st.multiselect(
            "Customer states",
            states,
            default=states
        )

    with f3:
        selected_statuses = st.multiselect(
            "Order statuses",
            statuses,
            default=statuses
        )

    f4, f5 = st.columns(2)

    with f4:
        selected_payments = st.multiselect(
            "Payment types",
            payment_types,
            default=payment_types,
            format_func=payment_label
        )

    with f5:
        value_range = st.slider(
            "Order total range",
            min_value=float(date_info["min_total"]),
            max_value=float(date_info["max_total"]),
            value=(float(date_info["min_total"]), float(date_info["max_total"]))
        )

if len(date_range) != 2:
    st.warning("Please select a valid date range.")
    st.stop()

match_filter = build_match(
    date_range[0],
    date_range[1],
    selected_states,
    selected_statuses,
    selected_payments,
    value_range[0],
    value_range[1]
)

base_filter_without_status = build_match(
    date_range[0],
    date_range[1],
    selected_states,
    [],
    selected_payments,
    value_range[0],
    value_range[1]
)

kpi_result = order_agg([
    {"$match": match_filter},
    {
        "$group": {
            "_id": None,
            "orders": {"$sum": 1},
            "revenue": {"$sum": "$order_total"},
            "freight": {"$sum": "$freight_total"},
            "payments": {"$sum": "$payment_total"},
            "avg_order": {"$avg": "$order_total"},
            "avg_review": {"$avg": "$review_score"},
            "late_orders": {
                "$sum": {"$cond": [{"$gt": ["$delivery_delay_days", 0]}, 1, 0]}
            },
            "high_freight_orders": {
                "$sum": {"$cond": [{"$gt": ["$freight_total", 50]}, 1, 0]}
            }
        }
    }
])

kpi = kpi_result[0] if kpi_result else {}

orders_count = int(kpi.get("orders", 0) or 0)
revenue = float(kpi.get("revenue", 0) or 0)
freight = float(kpi.get("freight", 0) or 0)
payments_total = float(kpi.get("payments", 0) or 0)
avg_order = float(kpi.get("avg_order", 0) or 0)
avg_review = float(kpi.get("avg_review", 0) or 0)
late_orders = int(kpi.get("late_orders", 0) or 0)
high_freight_orders = int(kpi.get("high_freight_orders", 0) or 0)
late_rate = (late_orders / orders_count * 100) if orders_count else 0

problem_orders = order_agg([
    {
        "$match": {
            **base_filter_without_status,
            "order_status": {"$in": ["canceled", "unavailable", "processing", "shipped", "created", "invoiced"]}
        }
    },
    {"$group": {"_id": "$order_status", "orders": {"$sum": 1}}},
    {"$sort": {"orders": -1}}
])

problem_total = sum(item["orders"] for item in problem_orders)
score = health_score(late_rate, problem_total, orders_count, avg_review)

k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    kpi_card("Health Score", f"{score}/100", "Based on delivery, status, and reviews")
with k2:
    kpi_card("Orders", f"{orders_count:,}", "Filtered orders")
with k3:
    kpi_card("Revenue", short_money(revenue), money(revenue))
with k4:
    kpi_card("Average Order", money(avg_order), "Mean order value")
with k5:
    kpi_card("Late Rate", f"{late_rate:.1f}%", f"{late_orders:,} late orders")
with k6:
    kpi_card("Non-delivered", f"{problem_total:,}", "Operational exceptions")

st.caption("All values are read from MongoDB collections created during migration. PostgreSQL is not used by this dashboard.")
st.divider()

top_state = order_agg([
    {"$match": match_filter},
    {"$group": {"_id": "$customer.state", "revenue": {"$sum": "$order_total"}, "orders": {"$sum": 1}}},
    {"$sort": {"revenue": -1}},
    {"$limit": 1}
])
top_state = top_state[0] if top_state else {}

best_month = order_agg([
    {"$match": match_filter},
    {"$group": {"_id": "$order_month", "revenue": {"$sum": "$order_total"}, "orders": {"$sum": 1}}},
    {"$sort": {"revenue": -1}},
    {"$limit": 1}
])
best_month = best_month[0] if best_month else {}

top_category = product_agg([
    {"$group": {"_id": "$category", "revenue": {"$sum": "$product_revenue"}, "units": {"$sum": "$units_sold"}}},
    {"$sort": {"revenue": -1}},
    {"$limit": 1}
])
top_category = top_category[0] if top_category else {}

i1, i2, i3, i4 = st.columns(4)

with i1:
    insight_card(
        "Top Revenue State",
        top_state.get("_id", "N/A"),
        f"{money(top_state.get('revenue', 0))} from {top_state.get('orders', 0):,} orders."
    )

with i2:
    insight_card(
        "Best Revenue Month",
        best_month.get("_id", "N/A"),
        f"{money(best_month.get('revenue', 0))} from {best_month.get('orders', 0):,} orders."
    )

with i3:
    insight_card(
        "Top Category",
        top_category.get("_id", "N/A"),
        f"{money(top_category.get('revenue', 0))} revenue and {top_category.get('units', 0):,} units."
    )

with i4:
    insight_card(
        "Payment Note",
        "Boleto",
        "Boleto is a Brazilian payment slip/voucher used in the source dataset."
    )

st.divider()

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Executive",
    "Revenue Quality",
    "Product Portfolio",
    "Customer Value",
    "Delivery Risk",
    "Order Inspector",
    "Migration Quality"
])

with tab1:
    st.subheader("Executive View")

    monthly = df_from(order_agg([
        {"$match": match_filter},
        {"$group": {"_id": "$order_month", "revenue": {"$sum": "$order_total"}, "orders": {"$sum": 1}, "avg_order": {"$avg": "$order_total"}}},
        {"$sort": {"_id": 1}}
    ]))

    if not monthly.empty:
        monthly = monthly.rename(columns={"_id": "month"})

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=monthly["month"],
            y=monthly["revenue"],
            mode="lines+markers",
            name="Revenue",
            line=dict(width=3)
        ))
        fig = chart_style(fig, 430)
        fig.update_layout(title="Revenue Trend", xaxis_title="Month", yaxis_title="Revenue")
        st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)

    with left:
        state_revenue = df_from(order_agg([
            {"$match": match_filter},
            {"$group": {"_id": "$customer.state", "revenue": {"$sum": "$order_total"}, "orders": {"$sum": 1}}},
            {"$sort": {"revenue": -1}},
            {"$limit": 15}
        ]))

        if not state_revenue.empty:
            state_revenue = state_revenue.rename(columns={"_id": "state"})
            fig_state = px.bar(state_revenue, x="state", y="revenue", hover_data=["orders"], title="Revenue by State")
            fig_state = chart_style(fig_state, 400)
            st.plotly_chart(fig_state, use_container_width=True)

    with right:
        problem_df = df_from(problem_orders)

        if not problem_df.empty:
            problem_df = problem_df.rename(columns={"_id": "status"})
            fig_problem = px.bar(problem_df, x="orders", y="status", orientation="h", title="Non-delivered Orders by Status")
            fig_problem.update_layout(yaxis={"categoryorder": "total ascending"})
            fig_problem = chart_style(fig_problem, 400)
            st.plotly_chart(fig_problem, use_container_width=True)
        else:
            st.success("No non-delivered orders in the selected data.")

with tab2:
    st.subheader("Revenue Quality")

    revenue_monthly = df_from(order_agg([
        {"$match": match_filter},
        {
            "$group": {
                "_id": "$order_month",
                "revenue": {"$sum": "$order_total"},
                "freight": {"$sum": "$freight_total"},
                "payments": {"$sum": "$payment_total"},
                "orders": {"$sum": 1},
                "avg_order": {"$avg": "$order_total"}
            }
        },
        {"$sort": {"_id": 1}}
    ]))

    if not revenue_monthly.empty:
        revenue_monthly = revenue_monthly.rename(columns={"_id": "month"})
        revenue_monthly["payment_gap"] = revenue_monthly["payments"] - (revenue_monthly["revenue"] + revenue_monthly["freight"])
        revenue_monthly["freight_share"] = revenue_monthly.apply(
            lambda row: (row["freight"] / row["revenue"] * 100) if row["revenue"] else 0,
            axis=1
        )

        stable_months = revenue_monthly[revenue_monthly["orders"] >= 100].copy()
        stable_months["growth_percent"] = stable_months["revenue"].pct_change() * 100
        stable_months["growth_percent"] = stable_months["growth_percent"].replace([float("inf"), -float("inf")], 0).fillna(0)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=revenue_monthly["month"],
            y=revenue_monthly["revenue"],
            mode="lines+markers",
            name="Order revenue",
            line=dict(width=3)
        ))
        fig.add_trace(go.Scatter(
            x=revenue_monthly["month"],
            y=revenue_monthly["payments"],
            mode="lines+markers",
            name="Payments",
            line=dict(width=3)
        ))
        fig.add_trace(go.Scatter(
            x=revenue_monthly["month"],
            y=revenue_monthly["freight"],
            mode="lines+markers",
            name="Freight",
            line=dict(width=3)
        ))
        fig = chart_style(fig, 430)
        fig.update_layout(
            title="Monthly Revenue, Payments, and Freight",
            xaxis_title="Month",
            yaxis_title="Value"
        )
        st.plotly_chart(fig, use_container_width=True)

        c1, c2, c3 = st.columns(3)

        total_gap = revenue_monthly["payment_gap"].sum()
        avg_freight_share = revenue_monthly[revenue_monthly["orders"] >= 100]["freight_share"].mean()
        best_month_row = revenue_monthly.sort_values("revenue", ascending=False).iloc[0]

        with c1:
            st.metric("Payment Gap", money(total_gap), "payments - revenue - freight")

        with c2:
            st.metric("Avg. Freight Share", f"{avg_freight_share:.1f}%", "months with 100+ orders")

        with c3:
            st.metric("Best Revenue Month", best_month_row["month"], money(best_month_row["revenue"]))

        left, right = st.columns(2)

        with left:
            growth_clean = stable_months.dropna(subset=["growth_percent"]).copy()
            growth_clean = growth_clean[growth_clean["growth_percent"].between(-100, 200)]

            fig_growth = px.bar(
                growth_clean,
                x="month",
                y="growth_percent",
                hover_data=["orders", "revenue"],
                title="Month-over-Month Revenue Growth"
            )
            fig_growth = chart_style(fig_growth, 390)
            fig_growth.update_layout(
                xaxis_title="Month",
                yaxis_title="Growth (%)"
            )
            st.plotly_chart(fig_growth, use_container_width=True)

        with right:
            freight_clean = revenue_monthly[revenue_monthly["orders"] >= 100].copy()

            fig_freight = px.line(
                freight_clean,
                x="month",
                y="freight_share",
                markers=True,
                hover_data=["orders", "revenue", "freight"],
                title="Freight Share of Revenue"
            )
            fig_freight = chart_style(fig_freight, 390)
            fig_freight.update_layout(
                xaxis_title="Month",
                yaxis_title="Freight share (%)"
            )
            st.plotly_chart(fig_freight, use_container_width=True)

        left2, right2 = st.columns(2)

        with left2:
            gap_df = revenue_monthly.copy()
            gap_df["absolute_gap"] = gap_df["payment_gap"].abs()
            gap_df = gap_df.sort_values("absolute_gap", ascending=False).head(12)

            fig_gap = px.bar(
                gap_df,
                x="month",
                y="payment_gap",
                hover_data=["revenue", "freight", "payments", "orders"],
                title="Largest Monthly Payment Gaps"
            )
            fig_gap = chart_style(fig_gap, 390)
            fig_gap.update_layout(
                xaxis_title="Month",
                yaxis_title="Payment gap"
            )
            st.plotly_chart(fig_gap, use_container_width=True)

        with right2:
            payment_df = df_from(order_agg([
                {"$match": match_filter},
                {"$project": {"payment_types": {"$split": [{"$ifNull": ["$payment_types", "unknown"]}, ", "]}}},
                {"$unwind": "$payment_types"},
                {"$group": {"_id": "$payment_types", "orders": {"$sum": 1}}},
                {"$sort": {"orders": -1}}
            ]))

            if not payment_df.empty:
                payment_df = payment_df.rename(columns={"_id": "payment_type"})
                payment_df["payment_label"] = payment_df["payment_type"].apply(payment_label)

                fig_payment = px.bar(
                    payment_df,
                    x="payment_label",
                    y="orders",
                    title="Orders by Payment Type"
                )
                fig_payment = chart_style(fig_payment, 390)
                fig_payment.update_layout(
                    xaxis_title="Payment type",
                    yaxis_title="Orders"
                )
                st.plotly_chart(fig_payment, use_container_width=True)

        st.write("Monthly revenue quality table")
        table_cols = ["month", "orders", "revenue", "freight", "payments", "payment_gap", "freight_share", "avg_order"]
        quality_table = revenue_monthly[table_cols].copy()
        quality_table["freight_share"] = pd.to_numeric(quality_table["freight_share"], errors="coerce").fillna(0).round(2)
        quality_table["payment_gap"] = pd.to_numeric(quality_table["payment_gap"], errors="coerce").fillna(0).round(2)
        quality_table = quality_table.sort_values("month")
        st.dataframe(quality_table, use_container_width=True, hide_index=True)


with tab3:
    st.subheader("Product Portfolio")

    category_perf = df_from(product_agg([
        {"$group": {"_id": "$category", "revenue": {"$sum": "$product_revenue"}, "units": {"$sum": "$units_sold"}, "orders": {"$sum": "$order_count"}}},
        {"$sort": {"revenue": -1}}
    ]))

    if not category_perf.empty:
        category_perf = category_perf.rename(columns={"_id": "category"})
        category_perf["revenue_share"] = category_perf["revenue"] / category_perf["revenue"].sum() * 100
        category_perf["cumulative_share"] = category_perf["revenue_share"].cumsum()

        left, right = st.columns(2)

        with left:
            top_categories = category_perf.head(12)
            fig_cat = px.bar(top_categories, x="revenue", y="category", orientation="h", hover_data=["units", "orders", "revenue_share"], title="Top Categories by Revenue")
            fig_cat.update_layout(yaxis={"categoryorder": "total ascending"})
            fig_cat = chart_style(fig_cat, 500)
            st.plotly_chart(fig_cat, use_container_width=True)

        with right:
            pareto = category_perf.head(25)
            fig_pareto = go.Figure()
            fig_pareto.add_trace(go.Bar(x=pareto["category"], y=pareto["revenue"], name="Revenue"))
            fig_pareto.add_trace(go.Scatter(x=pareto["category"], y=pareto["cumulative_share"], yaxis="y2", name="Cumulative Share (%)", mode="lines+markers"))
            fig_pareto.update_layout(
                title="Category Pareto Analysis",
                yaxis=dict(title="Revenue"),
                yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 110]),
                xaxis=dict(tickangle=-45)
            )
            fig_pareto = chart_style(fig_pareto, 500)
            st.plotly_chart(fig_pareto, use_container_width=True)

    top_products = df_from(product_agg([
        {"$sort": {"product_revenue": -1}},
        {"$limit": 30},
        {"$project": {"_id": 0, "product_id": 1, "category": 1, "product_revenue": 1, "units_sold": 1, "order_count": 1, "freight_revenue": 1}}
    ]))

    if not top_products.empty:
        st.dataframe(top_products, use_container_width=True, hide_index=True)

with tab4:
    st.subheader("Customer Value")

    top_customers = df_from(customer_agg([
        {"$sort": {"lifetime_value": -1}},
        {"$limit": 20},
        {"$project": {"_id": 0, "customer_unique_id": 1, "city": 1, "state": 1, "total_orders": 1, "lifetime_value": 1, "average_order_value": 1}}
    ]))

    if not top_customers.empty:
        fig_customers = px.bar(top_customers, x="lifetime_value", y="customer_unique_id", orientation="h", hover_data=["city", "state", "total_orders", "average_order_value"], title="Top Customers by Lifetime Value")
        fig_customers.update_layout(yaxis={"categoryorder": "total ascending"})
        fig_customers = chart_style(fig_customers, 500)
        st.plotly_chart(fig_customers, use_container_width=True)

    state_customers = df_from(customer_agg([
        {"$group": {"_id": "$state", "customers": {"$sum": 1}, "lifetime_value": {"$sum": "$lifetime_value"}, "avg_order_value": {"$avg": "$average_order_value"}}},
        {"$sort": {"lifetime_value": -1}},
        {"$limit": 15}
    ]))

    if not state_customers.empty:
        state_customers = state_customers.rename(columns={"_id": "state"})
        fig_state_customers = px.bar(state_customers, x="state", y="lifetime_value", hover_data=["customers", "avg_order_value"], title="Customer Value by State")
        fig_state_customers = chart_style(fig_state_customers, 420)
        st.plotly_chart(fig_state_customers, use_container_width=True)

with tab5:
    st.subheader("Delivery Risk")

    delivery_docs = list(db.orders_analytics.find(
        {**match_filter, "delivery_delay_days": {"$ne": None}},
        {"_id": 0, "order_month": 1, "delivery_days": 1, "delivery_delay_days": 1, "order_id": 1, "order_status": 1, "customer": 1}
    ).limit(90000))

    delivery = pd.DataFrame(delivery_docs)

    if delivery.empty:
        st.info("No delivery data available for the selected filters.")
    else:
        delivery["state"] = delivery["customer"].apply(lambda x: x.get("state") if isinstance(x, dict) else None)
        delivery["is_late"] = delivery["delivery_delay_days"] > 0

        d1, d2 = st.columns(2)

        with d1:
            fig_delay = px.histogram(delivery, x="delivery_delay_days", nbins=70, title="Delivery Delay Distribution")
            fig_delay = chart_style(fig_delay, 400)
            st.plotly_chart(fig_delay, use_container_width=True)

        with d2:
            state_risk = (
                delivery
                .groupby("state", as_index=False)
                .agg(
                    orders=("order_id", "count"),
                    late_orders=("is_late", "sum"),
                    avg_delay=("delivery_delay_days", "mean")
                )
            )
            state_risk["late_rate"] = state_risk["late_orders"] / state_risk["orders"] * 100
            state_risk = state_risk.sort_values("late_rate", ascending=False).head(15)

            fig_state_risk = px.bar(state_risk, x="state", y="late_rate", hover_data=["orders", "late_orders", "avg_delay"], title="Worst States by Late Delivery Rate")
            fig_state_risk = chart_style(fig_state_risk, 400)
            st.plotly_chart(fig_state_risk, use_container_width=True)

        late_month = (
            delivery
            .groupby("order_month", as_index=False)
            .agg(late_rate=("is_late", "mean"))
            .sort_values("order_month")
        )
        late_month["late_rate_percent"] = late_month["late_rate"] * 100

        fig_late = px.line(late_month, x="order_month", y="late_rate_percent", markers=True, title="Late Delivery Rate by Month")
        fig_late = chart_style(fig_late, 420)
        st.plotly_chart(fig_late, use_container_width=True)

        st.write("Highest delay orders")
        delay_table = delivery.sort_values("delivery_delay_days", ascending=False).head(20)
        st.dataframe(delay_table[["order_id", "order_status", "state", "delivery_days", "delivery_delay_days"]], use_container_width=True, hide_index=True)

with tab6:
    st.subheader("Order Inspector")

    search_order = st.text_input("Search order_id")

    if search_order:
        doc = db.orders_analytics.find_one({"order_id": search_order}, {"_id": 0})
    else:
        doc = db.orders_analytics.find_one(match_filter, {"_id": 0})

    if doc:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Order Status", doc.get("order_status", "N/A"))
        c2.metric("Order Total", money(doc.get("order_total", 0)))
        c3.metric("Payment Total", money(doc.get("payment_total", 0)))
        c4.metric("Delay Days", doc.get("delivery_delay_days", "N/A"))

        st.json(doc)
    else:
        st.warning("No order found.")

with tab7:
    st.subheader("Migration Quality")

    counts = {
        "orders_analytics": db.orders_analytics.count_documents({}),
        "customers_analytics": db.customers_analytics.count_documents({}),
        "products_analytics": db.products_analytics.count_documents({})
    }

    total_result = order_agg([
        {
            "$group": {
                "_id": None,
                "order_revenue": {"$sum": "$order_total"},
                "freight_total": {"$sum": "$freight_total"},
                "payment_total": {"$sum": "$payment_total"},
                "last_migration": {"$max": "$migrated_at"}
            }
        }
    ])

    totals = total_result[0] if total_result else {}

    q1, q2, q3 = st.columns(3)
    q1.metric("Order Documents", f"{counts['orders_analytics']:,}")
    q2.metric("Customer Documents", f"{counts['customers_analytics']:,}")
    q3.metric("Product Documents", f"{counts['products_analytics']:,}")

    q4, q5, q6 = st.columns(3)
    q4.metric("Order Revenue", money(totals.get("order_revenue", 0)))
    q5.metric("Freight Total", money(totals.get("freight_total", 0)))
    q6.metric("Payment Total", money(totals.get("payment_total", 0)))

    st.write("MongoDB indexes")

    index_rows = []
    for collection_name in ["orders_analytics", "customers_analytics", "products_analytics"]:
        for index in db[collection_name].list_indexes():
            index_rows.append({
                "collection": collection_name,
                "index": index.get("name"),
                "keys": str(index.get("key"))
            })

    st.dataframe(pd.DataFrame(index_rows), use_container_width=True, hide_index=True)

    sample_docs = list(db.orders_analytics.find({}, {"_id": 0}).limit(300))
    sample = pd.DataFrame(sample_docs)

    if not sample.empty and "customer" in sample.columns:
        customer_flat = pd.json_normalize(sample["customer"])
        customer_flat.columns = [f"customer_{col}" for col in customer_flat.columns]
        sample = pd.concat([sample.drop(columns=["customer"]), customer_flat], axis=1)

    default_cols = [
        col for col in [
            "order_id",
            "order_status",
            "order_month",
            "customer_city",
            "customer_state",
            "item_count",
            "order_total",
            "freight_total",
            "payment_total",
            "payment_types",
            "review_score",
            "delivery_days",
            "delivery_delay_days"
        ]
        if col in sample.columns
    ]

    selected_cols = st.multiselect("Preview columns", sample.columns.tolist(), default=default_cols)

    if selected_cols:
        st.dataframe(sample[selected_cols], use_container_width=True, hide_index=True)
        csv = sample[selected_cols].to_csv(index=False).encode("utf-8")
        st.download_button("Download preview data", csv, "mongodb_orders_preview.csv", "text/csv", use_container_width=True)

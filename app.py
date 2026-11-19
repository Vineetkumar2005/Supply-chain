from __future__ import annotations

from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from analytics import prepare_data, summarize, what_if_discount


st.set_page_config(
    page_title="Supply Chain Profitability",
    page_icon="📦",
    layout="wide",
)

st.title("Customer, Product & Profitability Performance")
st.caption("Commercial intelligence for supply-chain operations")

with st.sidebar:
    st.header("Data")
    uploaded = st.file_uploader("Upload the supply-chain CSV", type=("csv",))
    st.markdown(
        "Use the CSV from the project brief. The dashboard recognizes the "
        "DataCo-style column names, including `Sales`, `Order Profit Per Order`, "
        "`Customer Id`, `Category Name`, `Product Name`, `Market`, and `Order Region`."
    )

if uploaded is None:
    st.info(
        "Upload the dataset CSV to begin. No dataset is bundled with this project, "
        "so displayed results will come only from the file you provide."
    )
    st.subheader("Minimum financial fields")
    st.write(
        "- Revenue: `Sales` or `Order Item Total`\n"
        "- Profit: `Order Profit Per Order`, `Benefit per order`, or "
        "`Order Item Profit Ratio`"
    )
    st.stop()

try:
    raw = pd.read_csv(uploaded)
    data, metadata = prepare_data(raw)
except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
    st.error(f"Unable to use this file: {error}")
    st.stop()

with st.sidebar:
    st.header("Filters")
    segment_options = sorted(data["customer_segment"].unique())
    selected_segments = st.multiselect("Customer segment", segment_options, default=segment_options)
    category_options = sorted(data["category"].unique())
    selected_categories = st.multiselect("Category", category_options, default=category_options)
    product_options = sorted(data["product"].unique())
    selected_products = st.multiselect("Product", product_options, default=product_options)
    market_options = sorted(data["market"].unique())
    selected_markets = st.multiselect("Market", market_options, default=market_options)
    region_options = sorted(data["region"].unique())
    selected_regions = st.multiselect("Order region", region_options, default=region_options)
    max_discount = float(data["discount_rate"].max()) if not data.empty else 0.0
    discount_limit = st.slider(
        "Maximum discount rate (%)",
        min_value=0.0,
        max_value=max(1.0, max_discount * 100),
        value=max(1.0, max_discount * 100),
        format="%.0f%%",
    )

filtered = data.loc[
    data["customer_segment"].isin(selected_segments)
    & data["category"].isin(selected_categories)
    & data["product"].isin(selected_products)
    & data["market"].isin(selected_markets)
    & data["region"].isin(selected_regions)
    & data["discount_rate"].le(discount_limit / 100)
]
if filtered.empty:
    st.warning("No orders match the selected filters.")
    st.stop()

kpis = summarize(filtered)
st.caption(
    f"Showing {len(filtered):,} of {len(data):,} valid orders · "
    f"{metadata['removed_rows']:,} invalid rows excluded"
)

overview, customers_tab, products_tab, discounts_tab, data_tab = st.tabs(
    ["Revenue & Profit", "Customer Value", "Product & Category", "Discount Analyzer", "Data Quality"]
)

with overview:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total revenue", f"${kpis['revenue']:,.2f}")
    k2.metric("Total profit", f"${kpis['profit']:,.2f}")
    k3.metric("Profit margin", f"{kpis['margin']:.1%}")
    k4.metric("Customers", f"{kpis['customers']:,}")

    left, right = st.columns(2)
    with left:
        monthly = (
            filtered.groupby("order_month", as_index=False)[["sales", "profit"]].sum()
            if "order_month" in filtered
            else pd.DataFrame()
        )
        if not monthly.empty:
            trend = monthly.melt("order_month", var_name="Metric", value_name="Amount")
            st.plotly_chart(
                px.line(trend, x="order_month", y="Amount", color="Metric", markers=True, title="Revenue and profit by month"),
                width="stretch",
            )
        else:
            st.info("Add an `Order Date` column to enable monthly trends.")
    with right:
        regions = (
            filtered.groupby("region", as_index=False)[["sales", "profit"]]
            .sum()
            .sort_values("profit", ascending=False)
        )
        st.plotly_chart(
            px.bar(regions, x="region", y=["sales", "profit"], barmode="group", title="Revenue and profit by order region"),
            width="stretch",
        )

with customers_tab:
    customer_table = (
        filtered.groupby("customer_id", as_index=False)
        .agg(revenue=("sales", "sum"), profit=("profit", "sum"), orders=("sales", "size"))
        .sort_values("profit", ascending=False)
    )
    customer_table["margin"] = customer_table["profit"] / customer_table["revenue"]
    st.metric("Average profit per customer", f"${kpis['profit_per_customer']:,.2f}")
    positive, negative = st.columns(2)
    with positive:
        st.plotly_chart(
            px.bar(customer_table.head(10).sort_values("profit"), x="profit", y="customer_id", orientation="h", title="Top 10 customers by profit"),
            width="stretch",
        )
    with negative:
        st.plotly_chart(
            px.bar(customer_table.tail(10), x="profit", y="customer_id", orientation="h", title="Bottom 10 customers by profit"),
            width="stretch",
        )
    segment = (
        filtered.groupby("customer_segment", as_index=False)[["sales", "profit"]]
        .sum()
        .sort_values("profit", ascending=False)
    )
    st.plotly_chart(
        px.bar(segment, x="customer_segment", y=["sales", "profit"], barmode="group", title="Contribution by customer segment"),
        width="stretch",
    )
    st.dataframe(customer_table, width="stretch", hide_index=True)

with products_tab:
    category = (
        filtered.groupby("category", as_index=False)
        .agg(revenue=("sales", "sum"), profit=("profit", "sum"))
    )
    category["margin"] = category["profit"] / category["revenue"]
    product = (
        filtered.groupby(["product", "category"], as_index=False)
        .agg(revenue=("sales", "sum"), profit=("profit", "sum"))
    )
    product["margin"] = product["profit"] / product["revenue"]
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            px.bar(category.sort_values("margin"), x="margin", y="category", orientation="h", color="profit", title="Category margin"),
            width="stretch",
        )
    with right:
        st.plotly_chart(
            px.scatter(product, x="revenue", y="margin", size="revenue", color="margin", hover_name="product", title="Product revenue vs margin", color_continuous_scale="RdYlGn"),
            width="stretch",
        )
    st.dataframe(product.sort_values("profit"), width="stretch", hide_index=True)

with discounts_tab:
    discount_group = filtered.assign(
        discount_band=pd.cut(
            filtered["discount_rate"],
            bins=[-0.000001, 0.05, 0.10, 0.20, 0.30, float("inf")],
            labels=["0–5%", "5–10%", "10–20%", "20–30%", "30%+"],
        )
    )
    discount_summary = (
        discount_group.groupby("discount_band", observed=False, as_index=False)
        .agg(orders=("sales", "size"), margin=("margin", "mean"), profit=("profit", "sum"))
    )
    st.metric(
        "Discount impact ratio",
        f"{kpis['discount_impact_ratio']:.1f}%"
        if pd.notna(kpis["discount_impact_ratio"])
        else "Not available",
        help="Relative reduction in average margin for discounted orders versus non-discounted orders. Descriptive, not causal.",
    )
    st.plotly_chart(
        px.bar(discount_summary, x="discount_band", y="margin", color="orders", title="Average margin by discount band"),
        width="stretch",
    )
    st.caption("Discount impact ratio = max(0, (no-discount margin − discounted margin) / |no-discount margin|). It is an observational comparison and does not establish causation.")

    extra_discount = st.slider("What-if: additional discount", 0.0, 0.30, 0.0, 0.01, format="%.0f%%")
    scenario = what_if_discount(filtered, extra_discount)
    a, b, c = st.columns(3)
    a.metric("Scenario revenue", f"${scenario['revenue']:,.2f}")
    b.metric("Scenario profit", f"${scenario['profit']:,.2f}", f"${scenario['profit_change']:,.2f}")
    c.metric("Scenario margin", f"{scenario['margin']:.1%}")
    st.caption("Scenario assumes current costs stay fixed and the extra discount reduces both revenue and profit dollar-for-dollar.")

with data_tab:
    st.write(
        {
            "Rows uploaded": metadata["source_rows"],
            "Valid rows": metadata["valid_rows"],
            "Rows excluded (missing/non-finite financial values or non-positive revenue)": metadata["removed_rows"],
            "Revenue source": str(metadata["sales_source"]),
            "Profit source": str(metadata["profit_source"]),
        }
    )
    st.dataframe(filtered.head(500), width="stretch", hide_index=True)
    export = BytesIO()
    filtered.to_csv(export, index=False)
    st.download_button(
        "Download filtered orders as CSV",
        data=export.getvalue(),
        file_name="filtered_supply_chain_orders.csv",
        mime="text/csv",
    )

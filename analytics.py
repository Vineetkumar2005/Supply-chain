"""Data preparation and profitability metrics for the supply-chain dashboard."""

from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np
import pandas as pd


ALIASES: dict[str, tuple[str, ...]] = {
    "sales": ("order item total", "sales per customer", "sales", "revenue", "total sales"),
    "gross_sales": ("sales",),
    "profit": ("order profit per order", "benefit per order", "profit", "order profit"),
    "profit_ratio": ("order item profit ratio", "profit ratio", "profit margin"),
    "discount": ("order item discount", "discount amount"),
    "discount_rate": ("order item discount rate", "discount rate"),
    "customer_id": ("customer id", "order customer id", "customer"),
    "customer_segment": ("customer segment", "segment"),
    "category": ("category name", "product category", "category"),
    "product": ("product name", "product"),
    "market": ("market",),
    "region": ("order region", "region"),
    "country": ("order country", "customer country", "country"),
    "order_date": ("order date", "date"),
    "order_status": ("order status", "status"),
}

REQUIRED_METRICS = ("sales", "profit")


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _resolve_columns(columns: Iterable[object]) -> dict[str, object]:
    normalized = {_key(column): column for column in columns}
    result: dict[str, object] = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                result[canonical] = normalized[alias]
                break
    return result


def prepare_data(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    """Normalize supported columns and remove rows without valid financial values."""
    if frame.empty:
        raise ValueError("The uploaded CSV contains no rows.")

    columns = _resolve_columns(frame.columns)
    data = frame.copy()
    for canonical, source in columns.items():
        data[canonical] = frame[source]
    data = data.drop(columns=list(columns.values()), errors="ignore")
    if "gross_sales" not in data and "sales" in data:
        data["gross_sales"] = data["sales"]

    if "sales" not in columns and {
        "order item product price",
        "order item quantity",
    }.issubset({_key(column) for column in frame.columns}):
        source_by_key = {_key(column): column for column in frame.columns}
        price = pd.to_numeric(frame[source_by_key["order item product price"]], errors="coerce")
        quantity = pd.to_numeric(frame[source_by_key["order item quantity"]], errors="coerce")
        discount_source = source_by_key.get("order item discount")
        discount = (
            pd.to_numeric(frame[discount_source], errors="coerce").fillna(0)
            if discount_source is not None
            else 0
        )
        data["gross_sales"] = price * quantity
        data["sales"] = data["gross_sales"] - discount

    if "profit" not in data and "profit_ratio" in data and "sales" in data:
        data["profit"] = (
            pd.to_numeric(data["profit_ratio"], errors="coerce")
            * pd.to_numeric(data["sales"], errors="coerce")
        )

    missing = [column for column in REQUIRED_METRICS if column not in data]
    if missing:
        raise ValueError(
            "Could not identify required financial columns: "
            + ", ".join(missing)
            + ". Include Sales (or Order Item Total) and Order Profit Per Order "
            "(or Benefit per order / Order Item Profit Ratio)."
        )

    for column in ("sales", "gross_sales", "profit", "discount", "discount_rate", "profit_ratio"):
        if column in data:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    original_rows = len(data)
    valid = (
        np.isfinite(data["sales"])
        & np.isfinite(data["profit"])
        & data["sales"].gt(0)
    )
    data = data.loc[valid].copy()
    if data.empty:
        raise ValueError("No rows have both valid profit and positive sales.")

    if "discount_rate" not in data:
        if "discount" in data:
            data["discount_rate"] = data["discount"] / data["sales"]
        else:
            data["discount_rate"] = 0.0
    data["discount_rate"] = (
        pd.to_numeric(data["discount_rate"], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
        .clip(lower=0)
    )
    if data["discount_rate"].max(skipna=True) > 1:
        data["discount_rate"] = data["discount_rate"] / 100

    for column in (
        "customer_id",
        "customer_segment",
        "category",
        "product",
        "market",
        "region",
        "country",
        "order_status",
    ):
        if column not in data:
            data[column] = "Unknown"
        data[column] = data[column].fillna("Unknown").astype(str).str.strip()

    if "order_date" in data:
        data["order_date"] = pd.to_datetime(data["order_date"], errors="coerce")
        data["order_month"] = data["order_date"].dt.to_period("M").dt.to_timestamp()

    data["margin"] = data["profit"] / data["sales"]
    metadata: dict[str, object] = {
        "source_rows": original_rows,
        "valid_rows": len(data),
        "removed_rows": original_rows - len(data),
        "sales_source": columns.get("sales", "derived"),
        "profit_source": columns.get("profit", "derived from profit ratio" if "profit_ratio" in columns else "unknown"),
    }
    return data, metadata


def summarize(data: pd.DataFrame) -> dict[str, float | int]:
    """Calculate headline KPIs from already-filtered order rows."""
    revenue = float(data["sales"].sum())
    profit = float(data["profit"].sum())
    customers = int(data["customer_id"].nunique())
    no_discount = data.loc[data["discount_rate"].le(0), "margin"]
    discounted = data.loc[data["discount_rate"].gt(0), "margin"]
    baseline = float(no_discount.mean()) if not no_discount.empty else float("nan")
    discounted_margin = float(discounted.mean()) if not discounted.empty else float("nan")
    impact = (
        max(0.0, (baseline - discounted_margin) / abs(baseline) * 100)
        if np.isfinite(baseline) and np.isfinite(discounted_margin) and baseline != 0
        else float("nan")
    )
    return {
        "revenue": revenue,
        "gross_sales": float(data["gross_sales"].sum()),
        "profit": profit,
        "margin": profit / revenue if revenue else 0.0,
        "customers": customers,
        "profit_per_customer": profit / customers if customers else 0.0,
        "discount_impact_ratio": impact,
    }


def what_if_discount(data: pd.DataFrame, additional_discount_rate: float) -> dict[str, float]:
    """Estimate the effect of an extra discount, assuming current costs stay fixed."""
    extra_discount = data["sales"] * additional_discount_rate
    revenue = float((data["sales"] - extra_discount).sum())
    profit = float((data["profit"] - extra_discount).sum())
    return {
        "revenue": revenue,
        "profit": profit,
        "margin": profit / revenue if revenue else 0.0,
        "profit_change": profit - float(data["profit"].sum()),
    }

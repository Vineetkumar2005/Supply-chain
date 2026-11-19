# Supply Chain Profitability Performance

A Streamlit analytics project for customer, product, discount, and regional profitability using the supply-chain dataset described in the project brief.

## Start the dashboard

1. Create and activate a Python virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `streamlit run app.py`
4. Upload the CSV dataset in the sidebar.

The project does not bundle the linked dataset. Upload the downloaded CSV from the project brief; no results are shown until a dataset is supplied.

## Expected data

Revenue and profit are required. Supported revenue fields are `Sales` and `Order Item Total`. Supported profit fields are `Order Profit Per Order`, `Benefit per order`, and `Profit`. If profit is absent but `Order Item Profit Ratio` is present, profit is estimated as sales multiplied by that ratio. Common DataCo column names are recognized for customer, product, category, segment, market, region, country, discount, and order date.

Rows with missing/non-numeric financial values or non-positive revenue are excluded. Negative profit is retained because loss-making orders are analytically meaningful. Unknown optional dimensions are grouped as `Unknown`. Monthly trends appear when `Order Date` is present.

## Dashboard

- **Revenue & Profit:** sales, profit, margin, customer count, and monthly/region trends.
- **Customer Value:** profitable and loss-making customers, customer segment contribution, and customer-level table.
- **Product & Category:** category margin, product revenue-versus-margin view, and product table.
- **Discount Analyzer:** average margin by discount band, observational discount impact ratio, and a configurable extra-discount scenario.
- **Data Quality:** records excluded, source metric fields, filtered data preview, and CSV export.

The what-if model assumes an additional discount reduces revenue and profit dollar-for-dollar while current costs remain unchanged. The discount impact ratio compares discounted and non-discounted average order margins; it is descriptive and is not evidence that discounts caused the difference.

## Validation

Run the analytics unit tests with:

```sh
python -m unittest discover -s tests
```

## Research and executive conclusions

No dataset was available in the workspace when this project was created, so it would be misleading to state empirical findings or recommendations as if they were measured. Use the dashboard with the supplied CSV to calculate the evidence. Review the lowest-profit customers, negative-margin products/categories, and high-revenue/low-margin markets before changing pricing, customer terms, or discount policy. Validate any proposed discount changes against cost and service constraints.

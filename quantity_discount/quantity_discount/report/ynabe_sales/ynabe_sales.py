# # Copyright (c) 2025, Mohamed AbdElSabour and contributors
# # For license information, please see license.txt


import frappe
from frappe.utils import flt


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 120},
        {
            "label": "Salesperson",
            "fieldname": "salesperson",
            "fieldtype": "Link",
            "options": "Sales Person",
            "width": 150,
        },
        {
            "label": "Warehouse",
            "fieldname": "warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 150,
        },
        {
            "label": "200m",
            "fieldname": "tara_200",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "330m",
            "fieldname": "tara_330",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "600m",
            "fieldname": "tara_600",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Sale Qty",
            "fieldname": "sale_qty",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Total Sale",
            "fieldname": "total_sale",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Cash Sale",
            "fieldname": "cash_sale",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Credit Sale",
            "fieldname": "credit_sale",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Bank Transfer",
            "fieldname": "online_transfer",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Cash Collection",
            "fieldname": "cash_collection",
            "fieldtype": "Currency",
            "width": 150,
        },
    ]


def get_data(filters):
    conditions = ""
    values = {}

    if filters.get("from_date") and filters.get("to_date"):
        conditions = " AND date BETWEEN %(from_date)s AND %(to_date)s"
        values.update(
            {"from_date": filters["from_date"], "to_date": filters["to_date"]}
        )

    query = f"""
        SELECT
            final.date,
            final.salesperson,
            final.warehouse,
            COALESCE(final.tara_200, 0) AS tara_200,
            COALESCE(final.tara_330, 0) AS tara_330,
            COALESCE(final.tara_600, 0) AS tara_600,
            COALESCE(final.sale_qty, 0) AS sale_qty,
            COALESCE(final.total_sale, 0) AS total_sale,
            COALESCE(final.cash_sale, 0) AS cash_sale,
            COALESCE(final.credit_sale, 0) AS credit_sale,
            COALESCE(final.online_transfer, 0) AS online_transfer,
            COALESCE(final.cash_collection, 0) AS cash_collection
        FROM (
            -- Sales Invoice Data
            SELECT
                DATE(si.posting_date) AS date,
                sp.name AS salesperson,
                w.name AS warehouse,
                SUM(IFNULL(qty.tara_200, 0)) AS tara_200,
                SUM(IFNULL(qty.tara_330, 0)) AS tara_330,
                SUM(IFNULL(qty.tara_600, 0)) AS tara_600,
                SUM(IFNULL(qty.total_qty, 0)) AS sale_qty,
				SUM(CASE WHEN si.status IN ('Unpaid','Paid', 'Overdue','Partly Paid') THEN IFNULL(si.rounded_total, si.grand_total) ELSE 0 END) AS total_sale,
                SUM(IFNULL(cash.total_cash, 0)) AS cash_sale,
                SUM(CASE WHEN si.status IN ('Unpaid', 'Overdue','Partly Paid') THEN IFNULL(si.outstanding_amount) ELSE 0 END) AS credit_sale,
                0 AS online_transfer,
                0 AS cash_collection
            FROM `tabSales Invoice` si
            LEFT JOIN `tabSales Person` sp ON sp.custom_user = si.sales_person
            LEFT JOIN `tabWarehouse` w ON w.custom_sales_person = sp.name
            LEFT JOIN (
                SELECT
                    parent,
                    SUM(CASE WHEN item_code = 'مياة ريفيرا 200m' THEN qty ELSE 0 END) AS tara_200,
                    SUM(CASE WHEN item_code = 'مياة ريفيرا 330m' THEN qty ELSE 0 END) AS tara_330,
                    SUM(CASE WHEN item_code = 'مياة ريفيرا 600m' THEN qty ELSE 0 END) AS tara_600,
                    (
                        SUM(CASE WHEN item_code = 'مياة ريفيرا 330m' THEN qty ELSE 0 END) +
                        SUM(CASE WHEN item_code = 'مياة ريفيرا 200m' THEN qty ELSE 0 END) +
                        SUM(CASE WHEN item_code = 'مياة ريفيرا 600m' THEN qty ELSE 0 END)
                    ) AS total_qty
                FROM `tabSales Invoice Item`
                GROUP BY parent
            ) qty ON qty.parent = si.name
            LEFT JOIN (
                SELECT parent, SUM(amount) AS total_cash
                FROM `tabSales Invoice Payment`
                WHERE (LOWER(mode_of_payment) LIKE '%%cash%%' OR LOWER(mode_of_payment) LIKE '%%نقد%%')
                GROUP BY parent
            ) cash ON cash.parent = si.name
            WHERE si.docstatus = 1
              AND si.sales_person IS NOT NULL
            GROUP BY DATE(si.posting_date), sp.name, w.name

            UNION ALL

            -- Payment Entry Data (Bank Transfer)
            SELECT
                DATE(pe.posting_date) AS date,
                sp.name AS salesperson,
                w.name AS warehouse,
                0 AS tara_200,
                0 AS tara_330,
                0 AS tara_600,
                0 AS sale_qty,
                0 AS total_sale,
                0 AS cash_sale,
                0 AS credit_sale,
                SUM(pe.paid_amount) AS online_transfer,
                0 AS cash_collection
            FROM `tabPayment Entry` pe
            LEFT JOIN `tabAccount` acc ON acc.name = pe.paid_to
            LEFT JOIN `tabUser` u ON u.name = acc.custom_user
            LEFT JOIN `tabSales Person` sp ON sp.custom_user = u.name
            LEFT JOIN `tabWarehouse` w ON w.custom_sales_person = sp.name
            WHERE pe.docstatus = 1
              AND pe.mode_of_payment LIKE '%%حوالة مصرفية%%'
              AND pe.workflow_state = 'Approved'
              AND acc.custom_user IS NOT NULL
            GROUP BY DATE(pe.posting_date), sp.name, w.name

            UNION ALL

            -- Payment Entry Data (Cash Collection)
            SELECT
                DATE(pe.posting_date) AS date,
                sp.name AS salesperson,
                w.name AS warehouse,
                0 AS tara_200,
                0 AS tara_330,
                0 AS tara_600,
                0 AS sale_qty,
                0 AS total_sale,
                0 AS cash_sale,
                0 AS credit_sale,
                0 AS online_transfer,
                SUM(pe.paid_amount) AS cash_collection
            FROM `tabPayment Entry` pe
            LEFT JOIN `tabAccount` acc ON acc.name = pe.paid_to
            LEFT JOIN `tabUser` u ON u.name = acc.custom_user
            LEFT JOIN `tabSales Person` sp ON sp.custom_user = u.name
            LEFT JOIN `tabWarehouse` w ON w.custom_sales_person = sp.name
            WHERE pe.docstatus = 1
              AND (pe.mode_of_payment LIKE '%%cash%%' OR pe.mode_of_payment LIKE '%%نقد%%')
              AND pe.workflow_state = 'Approved'
              AND acc.custom_user IS NOT NULL
            GROUP BY DATE(pe.posting_date), sp.name, w.name
        ) AS final
        WHERE final.salesperson IS NOT NULL
          AND final.warehouse IS NOT NULL
          {conditions}
        ORDER BY final.date, final.warehouse, final.salesperson
    """

    # Get the unioned data
    raw_data = frappe.db.sql(query, values, as_dict=True)

    # Group and aggregate the data
    grouped_data = {}
    for row in raw_data:
        key = (row["date"], row["salesperson"], row["warehouse"])
        if key not in grouped_data:
            grouped_data[key] = {
                "date": row["date"],
                "salesperson": row["salesperson"],
                "warehouse": row["warehouse"],
                "tara_200": 0,
                "tara_330": 0,
                "tara_600": 0,
                "sale_qty": 0,
                "total_sale": 0,
                "cash_sale": 0,
                "credit_sale": 0,
                "online_transfer": 0,
                "cash_collection": 0,
            }

        # Sum all values
        for field in [
            "tara_200",
            "tara_330",
            "tara_600",
            "sale_qty",
            "total_sale",
            "cash_sale",
            "credit_sale",
            "online_transfer",
            "cash_collection",
        ]:
            grouped_data[key][field] += flt(row[field])

    return list(grouped_data.values())

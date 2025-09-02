import frappe


def set_qty_discount(doc, method):
    settings = frappe.get_single("Discount Settings")
    if not settings.enable_quantity_discount:
        return
    rules = settings.get("discount_settings_items") or []
    if not rules:
        frappe.throw("Please set quantity discount rules in Discount Settings")
    rules = sorted(rules, key=lambda x: x.from_qty)

    # find the  rate based on total_qty
    rate = None
    for rule in rules:
        if rule.from_qty <= doc.total_qty <= rule.to_qty:
            rate = rule.rate
            break

    if rate is not None:
        for d in doc.get("items"):
            d.rate = rate
            d.amount = d.qty * d.rate

        # recalculate taxes and totals
        if hasattr(doc, "calculate_taxes_and_totals"):
            doc.calculate_taxes_and_totals()

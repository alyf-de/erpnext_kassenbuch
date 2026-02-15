// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cash Transaction", {
	type(frm) {
		if (frm.doc.type === "Pay") {
			frm.set_value("reference_type", "Purchase Invoice");
			frm.set_value("reference_name", "");
			frm.set_value("party_type", "");
			frm.set_value("party", "");
			frm.set_value("party_name", "");
		} else if (frm.doc.type === "Receive") {
			frm.set_value("reference_type", "Sales Invoice");
			frm.set_value("reference_name", "");
			frm.set_value("party_type", "");
			frm.set_value("party", "");
			frm.set_value("party_name", "");
		}
	},

	reference_name(frm) {
		if (!frm.doc.reference_type || !frm.doc.reference_name) {
			frm.set_value("party_type", "");
			frm.set_value("party", "");
			frm.set_value("party_name", "");
			return;
		}
		if (frm.doc.reference_type === "Sales Invoice") {
			frappe.db.get_value(
				"Sales Invoice",
				frm.doc.reference_name,
				["customer", "customer_name"],
				(r) => {
					if (r) {
						frm.set_value("party_type", "Customer");
						frm.set_value("party", r.customer);
						frm.set_value("party_name", r.customer_name);
					}
				}
			);
		} else if (frm.doc.reference_type === "Purchase Invoice") {
			frappe.db.get_value(
				"Purchase Invoice",
				frm.doc.reference_name,
				["supplier", "supplier_name"],
				(r) => {
					if (r) {
						frm.set_value("party_type", "Supplier");
						frm.set_value("party", r.supplier);
						frm.set_value("party_name", r.supplier_name);
					}
				}
			);
		}
	},
});

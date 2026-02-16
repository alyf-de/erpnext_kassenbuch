// Copyright (c) 2025, ALYF GmbH and contributors
// Add "Create > Cash Transaction" on Purchase Invoice (submitted, with outstanding).

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || flt(frm.doc.outstanding_amount) <= 0 || frm.doc.on_hold) {
			return;
		}
		if (!frappe.model.can_create("Cash Transaction")) {
			return;
		}
		frm.add_custom_button(
			__("Cash Transaction"),
			() => {
				frappe.new_doc("Cash Transaction", {
					type: "Pay",
					reference_type: "Purchase Invoice",
					reference_name: frm.doc.name,
					company: frm.doc.company,
					party_type: "Supplier",
					party: frm.doc.supplier,
					party_name: frm.doc.supplier_name,
					amount: frm.doc.outstanding_amount,
					date: frappe.datetime.get_today(),
				});
			},
			__("Create")
		);
	},
});

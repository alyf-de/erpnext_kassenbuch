# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt


def get_custom_fields():
	return {
		"Journal Entry": [
			{
				"fieldname": "custom_cash_transaction",
				"fieldtype": "Link",
				"insert_after": "remark",
				"label": "Cash Transaction",
				"options": "Cash Transaction",
				"read_only": 1,
				"no_copy": 1,
			},
		],
	}

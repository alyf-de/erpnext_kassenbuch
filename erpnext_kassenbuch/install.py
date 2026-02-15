# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.customize_form.customize_form import (
	docfield_properties,
	doctype_properties,
)
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from erpnext_kassenbuch.custom_fields import get_custom_fields
from erpnext_kassenbuch.property_setters import get_property_setters


def after_install():
	_make_custom_fields()
	_make_property_setters()
	frappe.db.commit()


def _make_custom_fields():
	create_custom_fields(get_custom_fields(), ignore_validate=True)


def _make_property_setters():
	for prop_setter in get_property_setters():
		if prop_setter[1]:
			for_doctype = False
			fieldtype = docfield_properties.get(prop_setter[2])
		else:
			for_doctype = True
			fieldtype = doctype_properties.get(prop_setter[2]) if prop_setter[2] != "field_order" else "Data"
		make_property_setter(*prop_setter[:4], fieldtype, for_doctype=for_doctype)

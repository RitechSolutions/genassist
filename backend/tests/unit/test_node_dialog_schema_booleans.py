from app.schemas.dynamic_form_schemas.nodes import NODE_DIALOG_SCHEMAS


def test_no_node_checkbox_is_required():
    required = [
        (node_type, field.name)
        for node_type, fields in NODE_DIALOG_SCHEMAS.items()
        for field in fields
        if field.type == "boolean" and field.required
    ]
    assert required == []

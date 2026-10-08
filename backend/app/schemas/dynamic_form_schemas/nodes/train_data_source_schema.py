from typing import List

from ..base import ConditionalField, FieldSchema

TRAIN_DATA_SOURCE_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="sourceType",
        type="select",
        label="Source Type",
        required=True,
        options=[
            {"label": "Database", "value": "datasource"},
            {"label": "Uploaded File", "value": "csv"},
        ],
    ),
    FieldSchema(
        name="dataSourceId",
        type="text",
        label="Data Source",
        required=True,
        conditional=ConditionalField(field="sourceType", value="datasource"),
    ),
    FieldSchema(
        name="query",
        type="text",
        label="Query",
        required=True,
        conditional=ConditionalField(field="sourceType", value="datasource"),
    ),
    FieldSchema(
        name="csvFileName",
        type="text",
        label="Uploaded File Name",
        required=False,
        conditional=ConditionalField(field="sourceType", value="csv"),
    ),
    FieldSchema(
        name="csvFilePath",
        type="text",
        label="Training File",
        required=True,
        alternative_names=["csvFileId"],
        conditional=ConditionalField(field="sourceType", value="csv"),
    ),
    FieldSchema(
        name="csvFileId",
        type="text",
        label="Uploaded File ID",
        required=False,
        conditional=ConditionalField(field="sourceType", value="csv"),
    ),
    FieldSchema(
        name="csvFileUrl",
        type="text",
        label="Uploaded File URL",
        required=False,
        conditional=ConditionalField(field="sourceType", value="csv"),
    ),
]

/// Models for dynamic form schemas used in chat interactions.

enum FormFieldType { text, number, select, boolean, date }

extension FormFieldTypeExtension on FormFieldType {
  String toJson() => name;

  static FormFieldType fromJson(String value) {
    switch (value) {
      case 'text':
        return FormFieldType.text;
      case 'number':
        return FormFieldType.number;
      case 'select':
        return FormFieldType.select;
      case 'boolean':
        return FormFieldType.boolean;
      case 'date':
        return FormFieldType.date;
      default:
        return FormFieldType.text;
    }
  }
}

class FormFieldSchema {
  final String name;
  final FormFieldType type;
  final String? label;
  final bool required;
  final String? placeholder;
  final String? description;
  final List<String>? options;

  const FormFieldSchema({
    required this.name,
    required this.type,
    this.label,
    this.required = false,
    this.placeholder,
    this.description,
    this.options,
  });

  factory FormFieldSchema.fromJson(Map<String, dynamic> json) {
    return FormFieldSchema(
      name: json['name'] as String,
      type: FormFieldTypeExtension.fromJson(json['type'] as String),
      label: json['label'] as String?,
      required: json['required'] as bool? ?? false,
      placeholder: json['placeholder'] as String?,
      description: json['description'] as String?,
      options: json['options'] != null
          ? (json['options'] as List<dynamic>).map((e) => e as String).toList()
          : null,
    );
  }
}

class FormSchema {
  final String? message;
  final List<FormFieldSchema> fields;
  final String? nodeId;

  const FormSchema({
    this.message,
    required this.fields,
    this.nodeId,
  });

  factory FormSchema.fromJson(Map<String, dynamic> json) {
    return FormSchema(
      message: json['message'] as String?,
      fields: (json['fields'] as List<dynamic>)
          .map((e) => FormFieldSchema.fromJson(e as Map<String, dynamic>))
          .toList(),
      nodeId: json['nodeId'] as String?,
    );
  }
}

import 'package:flutter/material.dart';
import '../models/chat_config.dart';
import '../models/form_schema.dart';

class DynamicForm extends StatefulWidget {
  final FormSchema formSchema;
  final GenAgentChatTheme? theme;
  final String variant;
  final void Function(Map<String, dynamic> values) onSubmit;
  final VoidCallback? onCancel;

  const DynamicForm({
    super.key,
    required this.formSchema,
    this.theme,
    this.variant = 'footer',
    required this.onSubmit,
    this.onCancel,
  });

  @override
  State<DynamicForm> createState() => _DynamicFormState();
}

class _DynamicFormState extends State<DynamicForm> {
  final _formKey = GlobalKey<FormState>();
  final Map<String, dynamic> _values = {};

  @override
  void initState() {
    super.initState();
    for (final field in widget.formSchema.fields) {
      switch (field.type) {
        case FormFieldType.boolean:
          _values[field.name] = false;
          break;
        case FormFieldType.number:
          _values[field.name] = '';
          break;
        default:
          _values[field.name] = '';
      }
    }
  }

  void _handleSubmit() {
    if (_formKey.currentState?.validate() ?? false) {
      _formKey.currentState?.save();
      final submitValues = Map<String, dynamic>.from(_values);
      // Convert numeric strings to numbers.
      for (final field in widget.formSchema.fields) {
        if (field.type == FormFieldType.number &&
            submitValues[field.name] is String) {
          final parsed = num.tryParse(submitValues[field.name] as String);
          if (parsed != null) {
            submitValues[field.name] = parsed;
          }
        }
      }
      widget.onSubmit(submitValues);
    }
  }

  @override
  Widget build(BuildContext context) {
    final primaryColor = widget.theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor;
    final isCard = widget.variant == 'card';

    final formContent = Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (widget.formSchema.message != null &&
              widget.formSchema.message!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                widget.formSchema.message!,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  fontFamily: widget.theme?.fontFamily,
                  color: widget.theme?.textColor ?? Colors.black87,
                ),
              ),
            ),
          ...widget.formSchema.fields.map((field) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _buildField(field, primaryColor),
              )),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              if (widget.onCancel != null)
                TextButton(
                  onPressed: widget.onCancel,
                  child: Text(
                    'Cancel',
                    style: TextStyle(fontFamily: widget.theme?.fontFamily),
                  ),
                ),
              const SizedBox(width: 8),
              ElevatedButton(
                onPressed: _handleSubmit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: primaryColor,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                child: Text(
                  'Submit',
                  style: TextStyle(fontFamily: widget.theme?.fontFamily),
                ),
              ),
            ],
          ),
        ],
      ),
    );

    if (isCard) {
      return Card(
        margin: const EdgeInsets.all(12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        elevation: 2,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: formContent,
        ),
      );
    }

    // Footer variant.
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey[50],
        border: Border(top: BorderSide(color: Colors.grey[200]!)),
      ),
      child: formContent,
    );
  }

  Widget _buildField(FormFieldSchema field, Color primaryColor) {
    final label = field.label ?? field.name;

    switch (field.type) {
      case FormFieldType.text:
        return TextFormField(
          decoration: _inputDecoration(label, field.placeholder),
          style: _textStyle(),
          validator: field.required ? _requiredValidator(label) : null,
          onSaved: (value) => _values[field.name] = value ?? '',
        );

      case FormFieldType.number:
        return TextFormField(
          decoration: _inputDecoration(label, field.placeholder),
          style: _textStyle(),
          keyboardType:
              const TextInputType.numberWithOptions(decimal: true),
          validator: (value) {
            if (field.required && (value == null || value.trim().isEmpty)) {
              return '$label is required';
            }
            if (value != null && value.isNotEmpty && num.tryParse(value) == null) {
              return 'Please enter a valid number';
            }
            return null;
          },
          onSaved: (value) => _values[field.name] = value ?? '',
        );

      case FormFieldType.select:
        return DropdownButtonFormField<String>(
          decoration: _inputDecoration(label, null),
          style: _textStyle(),
          value: _values[field.name] is String &&
                  (_values[field.name] as String).isNotEmpty
              ? _values[field.name] as String
              : null,
          items: (field.options ?? []).map((option) {
            return DropdownMenuItem<String>(
              value: option,
              child: Text(option),
            );
          }).toList(),
          onChanged: (value) {
            setState(() => _values[field.name] = value ?? '');
          },
          validator: field.required
              ? (value) => (value == null || value.isEmpty)
                  ? '$label is required'
                  : null
              : null,
          onSaved: (value) => _values[field.name] = value ?? '',
        );

      case FormFieldType.boolean:
        return Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: TextStyle(
                  fontSize: 14,
                  fontFamily: widget.theme?.fontFamily,
                  color: widget.theme?.textColor ?? Colors.black87,
                ),
              ),
            ),
            Switch(
              value: _values[field.name] as bool? ?? false,
              activeColor: primaryColor,
              onChanged: (value) {
                setState(() => _values[field.name] = value);
              },
            ),
          ],
        );

      case FormFieldType.date:
        final currentValue = _values[field.name] as String?;
        return InkWell(
          onTap: () async {
            final picked = await showDatePicker(
              context: context,
              initialDate: DateTime.now(),
              firstDate: DateTime(2000),
              lastDate: DateTime(2100),
              builder: (context, child) {
                return Theme(
                  data: Theme.of(context).copyWith(
                    colorScheme: ColorScheme.light(primary: primaryColor),
                  ),
                  child: child!,
                );
              },
            );
            if (picked != null) {
              setState(() {
                _values[field.name] =
                    '${picked.year}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
              });
            }
          },
          child: InputDecorator(
            decoration: _inputDecoration(label, field.placeholder).copyWith(
              suffixIcon: const Icon(Icons.calendar_today, size: 20),
            ),
            child: Text(
              currentValue != null && currentValue.isNotEmpty
                  ? currentValue
                  : field.placeholder ?? 'Select date',
              style: TextStyle(
                fontSize: 14,
                fontFamily: widget.theme?.fontFamily,
                color: currentValue != null && currentValue.isNotEmpty
                    ? (widget.theme?.textColor ?? Colors.black87)
                    : Colors.grey[400],
              ),
            ),
          ),
        );
    }
  }

  InputDecoration _inputDecoration(String label, String? placeholder) {
    return InputDecoration(
      labelText: label,
      hintText: placeholder,
      labelStyle: TextStyle(fontFamily: widget.theme?.fontFamily),
      hintStyle: TextStyle(
        fontFamily: widget.theme?.fontFamily,
        color: Colors.grey[400],
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: Colors.grey[300]!),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: Colors.grey[300]!),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(
          color: widget.theme?.primaryColor ?? GenAgentChatTheme.defaultPrimaryColor,
        ),
      ),
    );
  }

  TextStyle _textStyle() {
    return TextStyle(
      fontSize: 14,
      fontFamily: widget.theme?.fontFamily,
      color: widget.theme?.textColor ?? Colors.black87,
    );
  }

  String? Function(String?) _requiredValidator(String label) {
    return (value) {
      if (value == null || value.trim().isEmpty) {
        return '$label is required';
      }
      return null;
    };
  }
}

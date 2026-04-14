/// Models for interactive chat content blocks (dynamic items, schedules, files, etc.).

class DynamicChatItem {
  final String id;
  final String? image;
  final String? type;
  final String? category;
  final String name;
  final String? description;
  final String? venueId;
  final List<String>? slots;
  String? selectedSlot;

  DynamicChatItem({
    required this.id,
    this.image,
    this.type,
    this.category,
    required this.name,
    this.description,
    this.venueId,
    this.slots,
    this.selectedSlot,
  });

  factory DynamicChatItem.fromJson(Map<String, dynamic> json) {
    return DynamicChatItem(
      id: json['id'] as String,
      image: json['image'] as String?,
      type: json['type'] as String?,
      category: json['category'] as String?,
      name: json['name'] as String,
      description: json['description'] as String?,
      venueId: json['venueId'] as String?,
      slots: json['slots'] != null
          ? (json['slots'] as List<dynamic>).map((e) => e as String).toList()
          : null,
      selectedSlot: json['selectedSlot'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      if (image != null) 'image': image,
      if (type != null) 'type': type,
      if (category != null) 'category': category,
      'name': name,
      if (description != null) 'description': description,
      if (venueId != null) 'venueId': venueId,
      if (slots != null) 'slots': slots,
      if (selectedSlot != null) 'selectedSlot': selectedSlot,
    };
  }
}

class ScheduleItem {
  final String id;
  final String? title;
  final List<DynamicChatItem> restaurants;

  const ScheduleItem({
    required this.id,
    this.title,
    required this.restaurants,
  });

  factory ScheduleItem.fromJson(Map<String, dynamic> json) {
    return ScheduleItem(
      id: json['id'] as String,
      title: json['title'] as String?,
      restaurants: (json['restaurants'] as List<dynamic>)
          .map((e) => DynamicChatItem.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      if (title != null) 'title': title,
      'restaurants': restaurants.map((e) => e.toJson()).toList(),
    };
  }
}

class FileItem {
  final String url;
  final String type;
  final String name;
  final String id;

  const FileItem({
    required this.url,
    required this.type,
    required this.name,
    required this.id,
  });

  factory FileItem.fromJson(Map<String, dynamic> json) {
    return FileItem(
      url: json['url'] as String,
      type: json['type'] as String,
      name: json['name'] as String,
      id: json['id'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'url': url,
      'type': type,
      'name': name,
      'id': id,
    };
  }
}

/// Sealed class hierarchy for chat content blocks.
sealed class ChatContentBlock {
  const ChatContentBlock();
}

class TextBlock extends ChatContentBlock {
  final String text;

  const TextBlock({required this.text});
}

class ItemsBlock extends ChatContentBlock {
  final List<DynamicChatItem> items;

  const ItemsBlock({required this.items});
}

class ScheduleBlock extends ChatContentBlock {
  final ScheduleItem schedule;

  const ScheduleBlock({required this.schedule});
}

class OptionsBlock extends ChatContentBlock {
  final List<String> options;

  const OptionsBlock({required this.options});
}

class FileBlock extends ChatContentBlock {
  final FileItem data;

  const FileBlock({required this.data});
}

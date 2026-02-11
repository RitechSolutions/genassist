import SwiftUI
import Foundation

// MARK: - Date/Time Utilities
struct SlotDisplayData {
    let day: String?
    let processedSlots: [String]
    let originalSlots: [String]
}

func processSlotsForDisplay(_ slots: [String]) -> SlotDisplayData {
    let dateFormatter = DateFormatter()
    dateFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
    dateFormatter.timeZone = TimeZone.current
    
    let displayDateFormatter = DateFormatter()
    displayDateFormatter.dateFormat = "MMM dd"
    displayDateFormatter.timeZone = TimeZone.current
    
    let timeFormatter = DateFormatter()
    timeFormatter.dateFormat = "HH:mm"
    timeFormatter.timeZone = TimeZone.current
    
    let dateTimeFormatter = DateFormatter()
    dateTimeFormatter.dateFormat = "MMMdd HH:mm"
    dateTimeFormatter.timeZone = TimeZone.current
    
    // Parse all slots and extract dates
    var parsedSlots: [(date: Date?, time: String, original: String)] = []
    var allDates: Set<String> = []
    
    for slot in slots {
        if let date = dateFormatter.date(from: slot) {
            let dateString = Calendar.current.startOfDay(for: date)
            let dateKey = dateFormatter.string(from: dateString).components(separatedBy: "T")[0]
            allDates.insert(dateKey)
            
            let timeString = timeFormatter.string(from: date)
            parsedSlots.append((date: date, time: timeString, original: slot))
        } else {
            // If parsing fails, treat as regular string
            parsedSlots.append((date: nil, time: slot, original: slot))
        }
    }
    
    // Check if all slots have the same date
    if allDates.count == 1, let firstDate = allDates.first {
        // All slots are on the same date
        let dayString = displayDateFormatter.string(from: dateFormatter.date(from: firstDate + "T00:00:00")!)
        let processedSlots = parsedSlots.map { $0.time }
        return SlotDisplayData(day: dayString, processedSlots: processedSlots, originalSlots: slots)
    } else {
        // Different dates - show date + time
        let processedSlots = parsedSlots.map { slotData in
            if let date = slotData.date {
                return dateTimeFormatter.string(from: date)
            } else {
                return slotData.original
            }
        }
        return SlotDisplayData(day: nil, processedSlots: processedSlots, originalSlots: slots)
    }
}

struct InteractiveChatItem: View {
    let messageText: String
    let configuration: ChatConfiguration
    let isUser: Bool
    let onDynamicItemTap: ((DynamicChatItem) -> Void)?
    let onOptionTap: ((String) -> Void)?
    let onItemSlotTap: ((DynamicChatItem, String) -> Void)?
    let onScheduleConfirm: ((ScheduleItem) -> Void)?
    let onMessageUpdate: ((String) -> Void)?
    let isLastMessage: Bool
    
    @State private var expandedItems: Set<String> = []
    @State private var expandedScheduleItems: Set<String> = []

    var body: some View {
        let blocks = parseInteractiveContentBlocks(messageText)
        VStack(alignment: .leading, spacing: configuration.dynamicItem.spacing) {
            ForEach(blocks, id: \.self) { block in
                blockView(for: block)
            }
        }
        .padding(.vertical, 4)
    }
    
    @ViewBuilder
    private func blockView(for block: ChatContentBlock) -> some View {
        switch block {
        case .text(let text):
            Text(text)
                .font(isUser ? configuration.senderMessage.textFont : configuration.receivedMessage.textFont)
        case .items(let items):
            ForEach(items) { item in
                DynamicItemView(
                    item: item,
                    configuration: configuration,
                    isExpanded: expandedItems.contains(item.id),
                    isRemovable: nil,
                    onTap: {
                        withAnimation(.easeInOut(duration: 0.3)) {
                            if expandedItems.contains(item.id) {
                                expandedItems.remove(item.id)
                            } else {
                                expandedItems.insert(item.id)
                            }
                        }
                    },
                    onItemTap: onDynamicItemTap,
                    onItemSlotTap: onItemSlotTap,
                    onItemDelete: nil,
                    isLastMessage: isLastMessage

                )
            }
        case .schedule(let scheduleItem):

            ScheduleItemView(
                initialScheduleItem: scheduleItem,
                configuration: configuration,
                isExpanded: true,
                onTap: {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        if expandedScheduleItems.contains(scheduleItem.id) {
                            expandedScheduleItems.remove(scheduleItem.id)
                        } else {
                            expandedScheduleItems.insert(scheduleItem.id)
                        }
                    }
                },
                onScheduleUpdate: { updatedScheduleItem in
                    // Update state directly
                    updateScheduleItemState(scheduleItem: updatedScheduleItem, restaurant: nil, selectedSlot: nil)
                },
                onScheduleConfirm: onScheduleConfirm,
                isLastMessage: isLastMessage
            )
        case .options(let options):
            OptionsView(
                options: options,
                configuration: configuration,
                onOptionTap: onOptionTap
            )
        }
    }
}

struct DynamicItemView: View {
    let item: DynamicChatItem
    let configuration: ChatConfiguration
    let isExpanded: Bool
    let isRemovable: Bool?
    let onTap: () -> Void
    let onItemTap: ((DynamicChatItem) -> Void)?
    let onItemSlotTap: ((DynamicChatItem, String) -> Void)?
    let onItemDelete: ((DynamicChatItem) -> Void)?
    let isLastMessage: Bool
    private var optimalLineLimit: Int {
        // Calculate line limit based on image height and spacing
        // Assuming each line is approximately 16-20 points high
        let lineHeight: CGFloat = 18
        let availableHeight = configuration.dynamicItem.imageSize
        var extraLines = 1
        if item.category != nil && !item.category!.isEmpty {
            extraLines = 2
        }
        let maxLines = max(1, Int(availableHeight / lineHeight) - extraLines) // -1 for title space

        return min(maxLines, 6) // Cap at 6 lines for reasonable UX
    }
    
    private var hasSlots: Bool {
        return item.slots != nil && !item.slots!.isEmpty
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: configuration.dynamicItem.spacing) {
            HStack(alignment: .top, spacing: configuration.dynamicItem.spacing) {
                // Image section - smaller when slots are available
                if let imageUrl = item.image, let url = URL(string: imageUrl) {
                    AsyncImage(url: url) { image in
                        image.resizable()
                    } placeholder: {
                        Color.gray
                    }
                    .frame(
                        width: hasSlots ? configuration.dynamicItem.imageSize * 0.7 : configuration.dynamicItem.imageSize,
                        height: hasSlots ? configuration.dynamicItem.imageSize * 0.7 : configuration.dynamicItem.imageSize
                    )
                    .cornerRadius(8)
                }
                
                // Text content section
                VStack(alignment: .leading, spacing: 4) {
                    // Item name with delete button on the same line
                    HStack {
                        Text(item.name)
                            .font(configuration.dynamicItem.titleFont)
                            .foregroundColor(configuration.dynamicItem.titleColor)
                            .lineLimit(2)
                            .truncationMode(.tail)
                        
                        Spacer()
                        
                        // Delete button (shown when isRemovable is true)
                        if isRemovable == true && isLastMessage == true{
                            Button(action: {
                                onItemDelete?(item)
                            }) {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.system(size: configuration.dynamicItem.deleteButtonSize))
                                    .foregroundColor(configuration.dynamicItem.deleteButtonColor)
                                    .background(
                                        Circle()
                                            .fill(configuration.dynamicItem.deleteButtonBackgroundColor)
                                            .frame(width: configuration.dynamicItem.deleteButtonSize + 4, height: configuration.dynamicItem.deleteButtonSize + 4)
                                    )
                            }
                            .buttonStyle(PlainButtonStyle())
                            .disabled(!isLastMessage)
                        }
                    }
                    if let category = item.category, !category.isEmpty {
                        Text(category)
                            .font(configuration.dynamicItem.descriptionFont)
                            .foregroundColor(configuration.dynamicItem.descriptionColor)
                            .lineLimit(isExpanded ? nil : optimalLineLimit)
                            .truncationMode(.tail)
                            .animation(.easeInOut(duration: 0.3), value: isExpanded)
                    }
                    
                    // Only show description when slots are NOT available
                    if let description = item.description, !description.isEmpty, !hasSlots {
                        Text(description)
                            .font(configuration.dynamicItem.descriptionFont)
                            .foregroundColor(configuration.dynamicItem.descriptionColor)
                            .lineLimit(isExpanded ? nil : optimalLineLimit)
                            .truncationMode(.tail)
                            .animation(.easeInOut(duration: 0.3), value: isExpanded)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            
            // Display slots if they exist - positioned under the photo and text content
            if item.slots != nil && !item.slots!.isEmpty {
                SlotsView(
                    slots: item.slots!,
                    selectedSlot: item.selectedSlot,
                    configuration: configuration,
                    onSlotTap: { slot in
                        onItemSlotTap?(item, slot)
                    },
                    isLastMessage: isLastMessage
                )
            }
        }
        .padding(configuration.dynamicItem.padding)
        .background(configuration.dynamicItem.backgroundColor)
        .cornerRadius(configuration.dynamicItem.cornerRadius)
        .frame(maxWidth: .infinity, alignment: .leading)
        .onTapGesture {
            onTap()
            onItemTap?(item)
        }
        .contentShape(Rectangle()) // Make the entire area tappable
    }
}

struct OptionsView: View {
    let options: [String]
    let configuration: ChatConfiguration
    let onOptionTap: ((String) -> Void)?
    
    @State private var selectedOption: String? = nil
    
    var body: some View {
        if configuration.optionsConfiguration.orientation == .vertical {
            VStack(alignment: .leading, spacing: configuration.optionsConfiguration.spacing) {
                ForEach(options, id: \.self) { option in
                    optionButton(for: option)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        } else {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: configuration.optionsConfiguration.spacing) {
                    ForEach(options, id: \.self) { option in
                        optionButton(for: option)
                    }
                }
                .padding(.horizontal, 4)
            }
        }
    }
    private func optionButton(for option: String) -> some View {
        
        Button(action: {
            selectedOption = option
            onOptionTap?(option)
        }) {
            Text(option)
                .font(configuration.optionsConfiguration.font)
                .foregroundColor(selectedOption == option ?
                                 configuration.optionsConfiguration.selectedColor :
                                    configuration.optionsConfiguration.textColor)
                .padding(.horizontal, configuration.optionsConfiguration.padding)
                .padding(.vertical, configuration.optionsConfiguration.padding/2)
                .background(selectedOption == option ?
                            configuration.optionsConfiguration.selectedBackgroundColor :
                                configuration.optionsConfiguration.backgroundColor)
                .cornerRadius(configuration.optionsConfiguration.cornerRadius)
        }
        .buttonStyle(PlainButtonStyle())
    }
}


struct SlotsView: View {
    let slots: [String]
    let selectedSlot: String?
    let configuration: ChatConfiguration
    let onSlotTap: ((String) -> Void)?
    let isLastMessage: Bool
    private var slotDisplayData: SlotDisplayData {
        processSlotsForDisplay(slots)
    }
 
    
    var body: some View {
        HStack(spacing: 4) {
            // Show day header if all slots are on the same date
            //if let day = slotDisplayData.day {
                Text(slotDisplayData.day ?? "Slots")
                    .font(configuration.dynamicItem.descriptionFont)
                    .foregroundColor(configuration.dynamicItem.descriptionColor)
                    .fontWeight(.medium)
            //}
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: configuration.dynamicItem.optionsConfiguration.spacing) {
                    ForEach(Array(slotDisplayData.processedSlots.enumerated()), id: \.offset) { index, processedSlot in
                        let originalSlot = slotDisplayData.originalSlots[index]
                        slotButton(for: processedSlot, originalSlot: originalSlot)

                    }
                }
                .padding(.horizontal, 4)
            }
        }
    }

    
    private func slotButton(for processedSlot: String, originalSlot: String) -> some View {
        Button(action: {
            onSlotTap?(originalSlot)
        }) {
            Text(processedSlot)
                .font(configuration.dynamicItem.optionsConfiguration.font)
                .foregroundColor(selectedSlot == originalSlot ?
                                 configuration.dynamicItem.optionsConfiguration.selectedColor :
                                    configuration.dynamicItem.optionsConfiguration.textColor)
                .padding(.horizontal, configuration.dynamicItem.optionsConfiguration.padding)
                .padding(.vertical, configuration.dynamicItem.optionsConfiguration.padding/2)
                .background(selectedSlot == originalSlot ?
                            configuration.dynamicItem.optionsConfiguration.selectedBackgroundColor :
                                configuration.dynamicItem.optionsConfiguration.backgroundColor)
                .cornerRadius(configuration.dynamicItem.optionsConfiguration.cornerRadius)
        }
        .buttonStyle(PlainButtonStyle())
        .disabled(!isLastMessage)
    }
}

struct ScheduleItemView: View {
    let initialScheduleItem: ScheduleItem
    let configuration: ChatConfiguration
    let isExpanded: Bool
    let onTap: () -> Void
    let onScheduleUpdate: ((ScheduleItem) -> Void)?
    let onScheduleConfirm: ((ScheduleItem) -> Void)?
    let isLastMessage: Bool
    
    @State private var scheduleItem: ScheduleItem
    @State private var hasChanges: Bool = false
    
    init(initialScheduleItem: ScheduleItem, configuration: ChatConfiguration, isExpanded: Bool, onTap: @escaping () -> Void, onScheduleUpdate: ((ScheduleItem) -> Void)?, onScheduleConfirm: ((ScheduleItem) -> Void)?, isLastMessage: Bool) {
        self.initialScheduleItem = initialScheduleItem
        self.configuration = configuration
        self.isExpanded = isExpanded
        self.onTap = onTap
        self.onScheduleUpdate = onScheduleUpdate
        self.onScheduleConfirm = onScheduleConfirm
        self.isLastMessage = isLastMessage
        self._scheduleItem = State(initialValue: initialScheduleItem)
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: configuration.dynamicItem.spacing) {
            // Schedule header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(initialScheduleItem.title ?? "Schedule")
                        .font(configuration.dynamicItem.titleFont)
                        .foregroundColor(configuration.dynamicItem.titleColor)
                        .fontWeight(.semibold)
                    if false {
                        Text("\(scheduleItem.restaurants.count) restaurants available")
                            .font(configuration.dynamicItem.descriptionFont)
                            .foregroundColor(configuration.dynamicItem.descriptionColor)
                    }
                }.padding(.leading,8)
                
                Spacer()
                if false {
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(.secondary)
                        .animation(.easeInOut(duration: 0.3), value: isExpanded)
                }
            }
            .padding(configuration.dynamicItem.padding)
            .background(configuration.dynamicItem.backgroundColor)
            .cornerRadius(configuration.dynamicItem.cornerRadius)
            .onTapGesture {
                onTap()
            }
            
            // Restaurant list (shown when expanded)
            if isExpanded {
                VStack(spacing: configuration.dynamicItem.spacing) {
                    ForEach(scheduleItem.restaurants) { restaurant in
                        HStack(spacing: 8) {
                            DynamicItemView(
                                item: restaurant,
                                configuration: configuration,
                                isExpanded: false,
                                isRemovable: true,
                                onTap: {},
                                onItemTap: { _ in
                                    // do nothing
                                },
                                onItemSlotTap: { item, slot in
                                    // Update internal state
                                    updateRestaurantSlot(restaurant: item, selectedSlot: slot)
                                    hasChanges = true
                                },
                                onItemDelete: { item in
                                    // Update internal state
                                    removeRestaurant(restaurant: item)
                                    hasChanges = true
                                },
                                isLastMessage: isLastMessage

                            )
                        }
                    }
                    
                    // Confirm button (shown when there are changes)
                    if isLastMessage {
                        Button(action: {
                            onScheduleConfirm?(scheduleItem)
                            hasChanges = false
                        }) {
                            HStack {
                                Image(systemName: "checkmark.circle.fill")
                                Text("Confirm")
                            }
                            .font(configuration.dynamicItem.titleFont)
                            .foregroundColor(.white)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 8)
                            .background(configuration.inputField.sendButtonColor)
                            .cornerRadius(8)
                        }
                        .buttonStyle(PlainButtonStyle())
                        .padding(.top, 8)
                    }
                    
                }
                .transition(.opacity.combined(with: .scale(scale: 0.95)))
            }
        }
        .animation(.easeInOut(duration: 0.3), value: isExpanded)
    }
    
    // MARK: - Internal State Management
    private func updateRestaurantSlot(restaurant: DynamicChatItem, selectedSlot: String) {
        let updatedRestaurants = scheduleItem.restaurants.map { restaurantItem in
            if restaurantItem.id == restaurant.id {
                return DynamicChatItem(
                    id: restaurantItem.id,
                    image: restaurantItem.image,
                    type: restaurantItem.type,
                    category: restaurantItem.category,
                    name: restaurantItem.name,
                    description: restaurantItem.description,
                    venueId: restaurantItem.venueId,
                    slots: restaurantItem.slots,
                    selectedSlot: selectedSlot
                )
            }
            return restaurantItem
        }
        
        scheduleItem = ScheduleItem(
            id: scheduleItem.id,
            title: scheduleItem.title,
            restaurants: updatedRestaurants
        )
        
        // Notify parent of the update
        onScheduleUpdate?(scheduleItem)
    }
    
    private func removeRestaurant(restaurant: DynamicChatItem) {
        let updatedRestaurants = scheduleItem.restaurants.filter { $0.id != restaurant.id }
        
        scheduleItem = ScheduleItem(
            id: scheduleItem.id,
            title: scheduleItem.title,
            restaurants: updatedRestaurants
        )
        
        // Notify parent of the update
        onScheduleUpdate?(scheduleItem)
    }
}

// MARK: - State Management Functions
extension InteractiveChatItem {
    private func updateScheduleItemState(scheduleItem: ScheduleItem, restaurant: DynamicChatItem?, selectedSlot: String?) {
        let blocks = parseInteractiveContentBlocks(messageText)
        let updatedBlocks = blocks.map { block in
            if case .schedule(let existingScheduleItem) = block, existingScheduleItem.id == scheduleItem.id {
                // Replace with the updated ScheduleItem from the component
                return ChatContentBlock.schedule(scheduleItem)
            }
            return block
        }
        
        let updatedContent = generateMessageContent(from: updatedBlocks)
        onMessageUpdate?(updatedContent)
    }
    
    
    private func generateMessageContent(from blocks: [ChatContentBlock]) -> String {
        var content = ""
        
        for block in blocks {
            switch block {
            case .text(let text):
                content += text
            case .items(let items):
                let jsonData = try? JSONEncoder().encode(items)
                if let jsonString = jsonData.flatMap({ String(data: $0, encoding: .utf8) }) {
                    content += "```json\n\(jsonString)\n```"
                }
            case .schedule(let scheduleItem):
                let jsonData = try? JSONEncoder().encode(scheduleItem)
                if let jsonString = jsonData.flatMap({ String(data: $0, encoding: .utf8) }) {
                    content += "```json\n\(jsonString)\n```"
                }
            case .options(let options):
                content += "***\(options.joined(separator: "; "))***"
            }
        }
        
        return content
    }
}

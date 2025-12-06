import Foundation

public struct DynamicChatItem: Identifiable, Decodable, Encodable, Hashable {
    public let id: String
    public let image: String?
    public let type: String?
    public let category: String?
    public let name: String
    public let description: String?
    public let venueId: String?
    public let slots: [String]?
    public let selectedSlot: String?
}

public struct ScheduleItem: Identifiable, Decodable, Encodable, Hashable {
    public let id: String
    public let title: String?
    public let restaurants: [DynamicChatItem]
}

public enum ChatContentBlock: Hashable {
    case text(String)
    case items([DynamicChatItem])
    case schedule(ScheduleItem)
    case options([String])
}

public func parseInteractiveContent(_ text: String) -> (String, [DynamicChatItem]?, String) {
    let pattern = #"(?s)(.*?)```json\s*(.*?)\s*```(.*)"#
    guard let regex = try? NSRegularExpression(pattern: pattern, options: []) else {
        return (text, nil, "")
    }
    let nsrange = NSRange(text.startIndex..<text.endIndex, in: text)
    if let match = regex.firstMatch(in: text, options: [], range: nsrange),
       let beforeRange = Range(match.range(at: 1), in: text),
       let jsonRange = Range(match.range(at: 2), in: text),
       let afterRange = Range(match.range(at: 3), in: text) {
        let before = String(text[beforeRange]).trimmingCharacters(in: .whitespacesAndNewlines)
        let jsonString = String(text[jsonRange])
        let after = String(text[afterRange]).trimmingCharacters(in: .whitespacesAndNewlines)
        let data = Data(jsonString.utf8)
        let items = try? JSONDecoder().decode([DynamicChatItem].self, from: data)
        return (before, items, after)
    }
    return (text, nil, "")
}

public func parseInteractiveContentBlocks(_ text: String) -> [ChatContentBlock] {
    let jsonPattern = #"(?s)```json\s*(.*?)\s*```"#
    let optionsPattern = #"\*\*\*(.*?)\*\*\*"#
    
    let jsonRegex = try? NSRegularExpression(pattern: jsonPattern, options: [])
    let optionsRegex = try? NSRegularExpression(pattern: optionsPattern, options: [])
    
    var results: [ChatContentBlock] = []
    var lastIndex = text.startIndex
    
    // Find all matches (both JSON and options)
    var allMatches: [(range: NSRange, type: String, content: String)] = []
    
    // Find JSON matches
    jsonRegex?.enumerateMatches(in: text, options: [], range: NSRange(text.startIndex..., in: text)) { match, _, _ in
        guard let match = match, let range = Range(match.range, in: text), let contentRange = Range(match.range(at: 1), in: text) else { return }
        allMatches.append((match.range, "json", String(text[contentRange])))
    }
    
    // Find options matches (time slots, events, restaurants, etc.)
    optionsRegex?.enumerateMatches(in: text, options: [], range: NSRange(text.startIndex..., in: text)) { match, _, _ in
        guard let match = match, let range = Range(match.range, in: text), let contentRange = Range(match.range(at: 1), in: text) else { return }
        allMatches.append((match.range, "options", String(text[contentRange])))
    }
    
    // Sort matches by position
    allMatches.sort { $0.range.location < $1.range.location }
    
    // Process matches
    for match in allMatches {
        guard let range = Range(match.range, in: text) else { continue }
        
        // Text before this match
        if lastIndex < range.lowerBound {
            let before = String(text[lastIndex..<range.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
            if !before.isEmpty {
                results.append(.text(before))
            }
        }
        
        // Process the match
        if match.type == "json" {
            let jsonString = match.content
            if let data = jsonString.data(using: .utf8) {
                // Try to decode as ScheduleItem first
                if let scheduleItem = try? JSONDecoder().decode(ScheduleItem.self, from: data) {
                    print("DEBUG: Successfully parsed ScheduleItem with \(scheduleItem.restaurants.count) restaurants")
                    results.append(.schedule(scheduleItem))
                }
                // If that fails, try to decode as array of DynamicChatItem
                else if let items = try? JSONDecoder().decode([DynamicChatItem].self, from: data) {
                    print("DEBUG: Successfully parsed DynamicChatItem array with \(items.count) items")
                    results.append(.items(items))
                } else {
                    print("DEBUG: Failed to parse JSON: \(jsonString)")
                }
            }
        } else if match.type == "options" {
            let optionsString = match.content
            let options = optionsString.split(separator: ";").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            if !options.isEmpty {
                results.append(.options(options))
            }
        }
        
        lastIndex = range.upperBound
    }
    
    // Any text after the last match
    if lastIndex < text.endIndex {
        let after = String(text[lastIndex...]).trimmingCharacters(in: .whitespacesAndNewlines)
        if !after.isEmpty {
            results.append(.text(after))
        }
    }
    
    return results
}

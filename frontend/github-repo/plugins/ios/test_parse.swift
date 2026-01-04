import Foundation

struct DynamicChatItem: Identifiable, Decodable, Encodable {
    let id: String
    let image: String?
    let type: String?
    let name: String
    let description: String?
    let slots: [String]?
    let selectedSlot: String?
}

struct ScheduleItem: Identifiable, Decodable, Encodable {
    let id: String
    let restaurants: [DynamicChatItem]
}

let jsonString = """
{"id":"67df29da-2d9c-453c-b7b9-7fb538275221","restaurants":[{"id":"5a4bf485da0c112a66ed6217","name":"Northwind Grill","slots":["2025-09-21T17:45:00","2025-09-21T18:00:00","2025-09-21T18:15:00","2025-09-21T18:30:00","2025-09-21T18:45:00","2025-09-21T19:00:00","2025-09-21T19:15:00","2025-09-21T20:00:00"],"selectedSlot":"2025-09-21T17:45:00"},{"id":"5a4bf485da0c112a66ed6263","name":"The Test Kitchen","slots":["2025-09-21T17:45:00","2025-09-21T18:00:00","2025-09-21T18:15:00","2025-09-21T18:30:00","2025-09-21T18:45:00","2025-09-21T19:00:00","2025-09-21T20:00:00"],"selectedSlot":"2025-09-21T17:45:00"}]}
"""

do {
    let data = jsonString.data(using: .utf8)!
    let scheduleItem = try JSONDecoder().decode(ScheduleItem.self, from: data)
    print("Successfully parsed ScheduleItem with \(scheduleItem.restaurants.count) restaurants")
    for restaurant in scheduleItem.restaurants {
        print("- \(restaurant.name) (ID: \(restaurant.id))")
    }
} catch {
    print("Error parsing JSON: \(error)")
}

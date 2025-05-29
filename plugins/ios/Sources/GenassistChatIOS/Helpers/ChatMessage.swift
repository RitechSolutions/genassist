import Foundation

public struct ChatMessage: Identifiable {
    public let id = UUID()
    public let content: String
    public let isUser: Bool
    public let timestamp: Date
    
    public init(content: String, isUser: Bool, timestamp: Date = Date()) {
        self.content = content
        self.isUser = isUser
        self.timestamp = timestamp
    }
} 

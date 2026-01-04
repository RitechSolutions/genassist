import Foundation

public struct ChatMessage: Identifiable {
    public let id: UUID
    public let content: String
    public let isUser: Bool
    public let timestamp: Date
    
    public init(id:UUID? = nil, content: String, isUser: Bool, timestamp: Date = Date()) {
        self.id = id ?? UUID()
        self.content = content
        self.isUser = isUser
        self.timestamp = timestamp
    }
}

public struct WelcomeScreenData: Identifiable {
    public let id = UUID()
    public let title: String
    public let description: String
    public let imageURL: String?
    public let possibleQueries: [String]
    
    public init(title: String, description: String, imageURL: String? = nil, possibleQueries: [String] = []) {
        self.title = title
        self.description = description
        self.imageURL = imageURL
        self.possibleQueries = possibleQueries
        
    }
} 

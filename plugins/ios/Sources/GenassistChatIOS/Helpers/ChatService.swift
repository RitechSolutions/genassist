import Foundation

public struct ChatMetadata: Codable {
    public let userInfo: [String: String]
    public let additionalData: [String: String]
    
    public init(userInfo: [String: String], additionalData: [String: String] = [:]) {
        self.userInfo = userInfo
        self.additionalData = additionalData
    }
}

public struct StartConversationResponse: Codable {
    public let message: String
    public let conversationId: String
    public let agentWelcomeMessage: String?
    public let agentPossibleQueries: [String]?
    
    enum CodingKeys: String, CodingKey {
        case message
        case conversationId = "conversation_id"
        case agentWelcomeMessage = "agent_welcome_message"
        case agentPossibleQueries = "agent_possible_queries"
    }
}

public struct Message: Codable, Sendable {
    public let createTime: String
    public let startTime: Double
    public let endTime: Double
    public let speaker: String
    public let text: String
    
    enum CodingKeys: String, CodingKey {
        case createTime = "create_time"
        case startTime = "start_time"
        case endTime = "end_time"
        case speaker
        case text
    }
    
    public var createDate: Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: createTime)
    }
    
    public func toJSON() -> [String: Any] {
        return [
            "create_time": createTime,
            "start_time": startTime,
            "end_time": endTime,
            "speaker": speaker,
            "text": text
        ]
    }
}

private actor WebSocketManager {
    private var webSocketTask: URLSessionWebSocketTask?
    private var isConnected = false
    
    func connect(url: URL) {
        print("WebSocket: Connecting to \(url)")
        webSocketTask = URLSession.shared.webSocketTask(with: url)
        webSocketTask?.resume()
        isConnected = true
        print("WebSocket: Connected")
    }
    
    func disconnect() {
        print("WebSocket: Disconnecting")
        webSocketTask?.cancel(with: .normalClosure, reason: nil)
        webSocketTask = nil
        isConnected = false
        print("WebSocket: Disconnected")
    }
    
    func receiveMessage() async throws -> Message? {
        guard isConnected, let task = webSocketTask else {
            print("WebSocket: Not connected or task is nil")
            return nil
        }
        
        print("WebSocket: Waiting for message...")
        let message = try await task.receive()
        print("WebSocket: Received message type: \(message)")
        
        switch message {
        case .string(let text):
            print("WebSocket: Received string message: \(text)")
            if let data = text.data(using: .utf8) {
                let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
                print("WebSocket: Parsed JSON: \(String(describing: json))")
                if let type = json?["type"] as? String,
                   type == "message",
                   let payload = json?["payload"] as? [String: Any] {
                    print("WebSocket: Found message payload")
                    let messageData = try JSONSerialization.data(withJSONObject: payload)
                    return try JSONDecoder().decode(Message.self, from: messageData)
                }
            }
        case .data(let data):
            print("WebSocket: Received data message of size: \(data.count)")
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            print("WebSocket: Parsed JSON: \(String(describing: json))")
            if let type = json?["type"] as? String,
               type == "message",
               let payload = json?["payload"] as? [String: Any] {
                print("WebSocket: Found message payload")
                let messageData = try JSONSerialization.data(withJSONObject: payload)
                return try JSONDecoder().decode(Message.self, from: messageData)
            }
        @unknown default:
            print("WebSocket: Received unknown message type")
            return nil
        }
        print("WebSocket: No valid message found in payload")
        return nil
    }
}

@MainActor
public class ChatService {
    private let baseURL: String
    private let apiKey: String
    private let metadata: ChatMetadata
    private var conversationId: String?
    private let webSocketManager = WebSocketManager()
    private var messageTask: Task<Void, Never>?
    private let storageKey = "genassist_conversation_id"
    private var possibleQueries: [String] = []
    private var messageHandler: ((Message) -> Void)?
    
    public init(baseURL: String, apiKey: String, metadata: ChatMetadata) {
        self.baseURL = baseURL.hasSuffix("/") ? String(baseURL.dropLast()) : baseURL
        self.apiKey = apiKey
        self.metadata = metadata
        loadSavedConversation()
    }
    
    public func setMessageHandler(_ handler: @escaping (Message) -> Void) {
        self.messageHandler = handler
    }
    
    public func getPossibleQueries() -> [String] {
        return possibleQueries
    }
    
    private func loadSavedConversation() {
        if let savedConversationId = UserDefaults.standard.string(forKey: storageKey) {
            self.conversationId = savedConversationId
            print("Loaded saved conversation:", savedConversationId)
        }
    }
    
    private func saveConversation() {
        if let conversationId = conversationId {
            UserDefaults.standard.set(conversationId, forKey: storageKey)
            print("Saved conversation:", conversationId)
        }
    }
    
    public func resetConversation() {
        messageTask?.cancel()
        messageTask = nil
        Task {
            await webSocketManager.disconnect()
        }
        conversationId = nil
        possibleQueries = []
        UserDefaults.standard.removeObject(forKey: storageKey)
    }
    
    public func hasActiveConversation() -> Bool {
        return conversationId != nil
    }
    
    public func getConversationId() -> String? {
        return conversationId
    }
    
    public func initializeConversation() async throws -> String {
        if let conversationId = conversationId {
            connectWebSocket()
            return conversationId
        }
        return try await startConversation()
    }
    
    public func startConversation() async throws -> String {
        let url = URL(string: "\(baseURL)/api/conversations/in-progress/start")!
        
        let requestBody: [String: Any] = [
            "messages": [],
            "recorded_at": ISO8601DateFormatter().string(from: Date()),
            "operator_id": "00000196-02d3-603c-994a-b616f314b0ba",
            "data_source_id": "00000196-02d3-6026-a041-ec8564d4a316"
        ]
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)
        
        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode(StartConversationResponse.self, from: data)
        
        self.conversationId = response.conversationId
        saveConversation()
        connectWebSocket()
        
        if let queries = response.agentPossibleQueries, !queries.isEmpty {
            self.possibleQueries = queries
        }
        
        if let welcomeMessage = response.agentWelcomeMessage, let handler = messageHandler {
            let now = Int64(Date().timeIntervalSince1970 * 1000)
            let message = Message(
                createTime: ISO8601DateFormatter().string(from: Date()),
                startTime: Double(now) / 1000,
                endTime: Double(now) / 1000 + 0.01,
                speaker: "agent",
                text: welcomeMessage
            )
            handler(message)
        }
        
        return response.conversationId
    }
    
    public func sendMessage(_ message: String) async throws {
        guard let conversationId = conversationId else {
            throw NSError(domain: "ChatService", code: -1, userInfo: [NSLocalizedDescriptionKey: "Conversation not started"])
        }
        
        let now = Int64(Date().timeIntervalSince1970 * 1000)
        let chatMessage = Message(
            createTime: ISO8601DateFormatter().string(from: Date()),
            startTime: Double(now) / 1000,
            endTime: Double(now) / 1000 + 0.01,
            speaker: "customer",
            text: message
        )
        
        let url = URL(string: "\(baseURL)/api/conversations/in-progress/update/\(conversationId)")!
        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "x-api-key")
        
        let body = ["messages": [chatMessage.toJSON()]]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (_, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw NSError(domain: "ChatService", code: -1, userInfo: [NSLocalizedDescriptionKey: "Failed to send message"])
        }
    }
    
    public func connectWebSocket() {
        guard let conversationId = conversationId else {
            print("WebSocket: No conversation ID available")
            return
        }
        
        let urlString = "\(baseURL.replacingOccurrences(of: "http://", with: "ws://"))/api/conversations/ws/\(conversationId)?api_key=\(apiKey)&lang=en&topics=message"
        guard let url = URL(string: urlString) else {
            print("WebSocket: Invalid URL: \(urlString)")
            return
        }
        
        print("WebSocket: Connecting to URL: \(urlString)")
        messageTask?.cancel()
        
        messageTask = Task {
            await webSocketManager.connect(url: url)
            
            while !Task.isCancelled {
                do {
                    if let message = try await webSocketManager.receiveMessage() {
                        print("WebSocket: Processing received message")
                        messageHandler?(message)
                    }
                } catch {
                    if !Task.isCancelled {
                        print("WebSocket error: \(error)")
                    }
                    break
                }
            }
        }
    }
    
    public func disconnect() {
        messageTask?.cancel()
        messageTask = nil
        Task {
            await webSocketManager.disconnect()
        }
    }
} 

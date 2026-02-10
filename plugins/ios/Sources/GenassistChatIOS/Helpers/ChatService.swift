import Foundation

public struct ChatMetadata: Codable {
    public let userInfo: [String: String]
    public let additionalData: [String: String]
    
    public init(userInfo: [String: String], additionalData: [String: String] = [:]) {
        self.userInfo = userInfo
        self.additionalData = additionalData
    }
    public func getMetadata() -> [String: String] {
        var metadata: [String: String] = userInfo
        metadata.merge(additionalData) { (_, new) in new }
        return metadata
    }
}

public struct StartConversationResponse: Codable {
    public let message: String
    public let agentId: String
    public let conversationId: String
    public let agentWelcomeMessage: String?
    public let agentWelcomeTitle: String?
    public let agentHasWelcomeImage: Bool?
    public let agentPossibleQueries: [String]?
    public let agentThinkingPhrases: [String]?
    
    enum CodingKeys: String, CodingKey {
        case message
        case agentId = "agent_id"
        case conversationId = "conversation_id"
        case agentWelcomeMessage = "agent_welcome_message"
        case agentWelcomeTitle = "agent_welcome_title"
        case agentHasWelcomeImage = "agent_has_welcome_image"
        case agentPossibleQueries = "agent_possible_queries"
        case agentThinkingPhrases = "agent_thinking_phrases"
    }
    public func toJSON() -> [String: Any] {
        return [
            "conversationId": conversationId,
            "agentWelcomeMessage": agentWelcomeMessage,
            "agentWelcomeTitle": agentWelcomeTitle,
            "agentHasWelcomeImage": agentHasWelcomeImage,
            "agentPossibleQueries": agentPossibleQueries,
            "agentThinkingPhrases": agentThinkingPhrases

        ]
    }
}
public struct AgentConfiguration: Identifiable, Decodable, Encodable {
    public let id = UUID()
    public let agentId: String
    public let conversationId: String
    public let agentWelcomeMessage: String?
    public let agentWelcomeTitle: String?
    public let agentWelcomeImage: String?
    public let agentPossibleQueries: [String]?
    public let agentThinkingPhrases: [String]?
    
    public init(agentId: String, conversationId: String, agentWelcomeMessage: String?, agentWelcomeTitle: String?, agentWelcomeImage: String?, agentPossibleQueries: [String]?, agentThinkingPhrases: [String]?) {
        self.agentId = agentId
        self.conversationId = conversationId
        self.agentWelcomeMessage = agentWelcomeMessage
        self.agentWelcomeTitle = agentWelcomeTitle
        self.agentWelcomeImage = agentWelcomeImage
        self.agentPossibleQueries = agentPossibleQueries
        self.agentThinkingPhrases = agentThinkingPhrases
    }
}
public struct Message: Codable, Sendable {
    public let createTime: String
    public let startTime: Double
    public let endTime: Double
    public let speaker: String
    public let text: String
    public let id: String?
    public let type: String?
    public let feedback: [String]?
    
    public init(createTime: String, startTime: Double, endTime: Double, speaker: String, text: String, id: String? = nil, type: String? = nil, feedback: [String]? = nil) {
        self.createTime = createTime
        self.startTime = startTime
        self.endTime = endTime
        self.speaker = speaker
        self.text = text
        self.id = id
        self.type = type
        self.feedback = feedback
    }
    
    enum CodingKeys: String, CodingKey {
        case createTime = "create_time"
        case startTime = "start_time"
        case endTime = "end_time"
        case speaker
        case text
        case id
        case type
        case feedback
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

public struct ConversationResponse: Codable {
    public let operatorId: String
    public let dataSourceId: String
    public let recordingId: String?
    public let transcription: String? // Can be null
    public let conversationDate: String
    public let customerId: String?
    public let threadId: String?
    public let wordCount: Int
    public let customerRatio: Int
    public let agentRatio: Int
    public let duration: Int
    public let status: String
    public let conversationType: String
    public let id: String
    public let createdAt: String
    public let updatedAt: String
    public let recording: String?
    public let analysis: String?
    public let inProgressHostilityScore: Int?
    public let supervisorId: String?
    public let topic: String?
    public let negativeReason: String?
    public let feedback: String?
    public let messages: [Message]?

    enum CodingKeys: String, CodingKey {
        case operatorId = "operator_id"
        case dataSourceId = "data_source_id"
        case recordingId = "recording_id"
        case transcription
        case conversationDate = "conversation_date"
        case customerId = "customer_id"
        case threadId = "thread_id"
        case wordCount = "word_count"
        case customerRatio = "customer_ratio"
        case agentRatio = "agent_ratio"
        case duration
        case status
        case conversationType = "conversation_type"
        case id
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case recording
        case analysis
        case inProgressHostilityScore = "in_progress_hostility_score"
        case supervisorId = "supervisor_id"
        case topic
        case negativeReason = "negative_reason"
        case feedback
        case messages
    }
}

private actor WebSocketManager {
    private var webSocketTask: URLSessionWebSocketTask?
    private var isConnected = false
    
    func connect(url: URL, headers: [String: String] = [:]) {
        print("WebSocket: Connecting to \(url)")
        var request = URLRequest(url: url)
        for (key, value) in headers {
            request.addValue(value, forHTTPHeaderField: key)
        }
        webSocketTask = URLSession.shared.webSocketTask(with: request)
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
    private let tenant: String?
    private let customerId: String?
    private var conversationId: String?
    private let webSocketManager = WebSocketManager()
    private var messageTask: Task<Void, Never>?
    
    private var storageKey: String {
        return "genassist_conversation_id\(keySuffix)"
    }
    
    private var lastStartTimeKey: String {
        return "genassist_last_start_conversation_time\(keySuffix)"
    }
    
    private var messagesKey: String {
        return "genassist_conversation_messages\(keySuffix)"
    }
    
    private var agentConfigKey: String {
        return "genassist_agent_config\(keySuffix)"
    }
    
    private var keySuffix: String {
        var components: [String] = []
        if let tenant = tenant {
            components.append("_tenant_\(tenant)")
        }
        if let customerId = customerId {
            components.append("_customer_\(customerId)")
        }
        return components.joined()
    }
    

    private var agentConfig: AgentConfiguration?
    
    private var messageHandler: ((Message) -> Void)?
    private var messages: [Message] = []
    private var lastStartConversationTime: Date? // Track last startConversation time
    private var startConversationPath: String?
    private var updateConversationPath: String?
    private let useWs: Bool
    
    public init(baseURL: String, apiKey: String, metadata: ChatMetadata, startConversationPath: String? = nil, updateConversationPath: String? = nil, useWs: Bool = true, tenant: String? = nil, customerId: String? = nil) {
        self.baseURL = baseURL.hasSuffix("/") ? String(baseURL.dropLast()) : baseURL
        self.apiKey = apiKey
        self.metadata = metadata
        self.startConversationPath = startConversationPath
        self.updateConversationPath = updateConversationPath
        self.useWs = useWs
        self.tenant = tenant
        self.customerId = customerId
        loadSavedConversation()
    }
    
    public func setMessageHandler(_ handler: @escaping (Message) -> Void) {
        self.messageHandler = { [weak self] message in
            self?.messages.append(message)
            self?.saveConversation()
            handler(message)
        }
        // self.messageHandler = handler
    }
    
    public func getPossibleQueries() -> [String] {
        return agentConfig?.agentPossibleQueries ?? []
    }
    
    public func getThinkingPhrases() -> [String] {
        return agentConfig?.agentThinkingPhrases ?? []
    }
    
    public func getWelcomeMessage() -> WelcomeScreenData? {
        let title = agentConfig?.agentWelcomeTitle ?? ""
        let queries = agentConfig?.agentPossibleQueries ?? []
        if let welcomeMessageText = agentConfig?.agentWelcomeMessage {
            return WelcomeScreenData(
                title: title,
                description: welcomeMessageText,
                imageURL: agentConfig?.agentWelcomeImage,
                possibleQueries: queries
            )
        }
        return nil
    }
    

    
    private func loadSavedConversation() {
        if let savedConversationId = UserDefaults.standard.string(forKey: storageKey) {
            self.conversationId = savedConversationId
            print("Loaded saved conversation:", savedConversationId)

           
        }
        if let lastStartTimeInterval = UserDefaults.standard.object(forKey: lastStartTimeKey) as? Double {
            self.lastStartConversationTime = Date(timeIntervalSince1970: lastStartTimeInterval)
            print("Loaded last startConversation time: \(self.lastStartConversationTime!)")
        }
        if let messagesData = UserDefaults.standard.data(forKey: messagesKey) {
            do {
                let decodedMessages = try JSONDecoder().decode([Message].self, from: messagesData)
                self.messages = decodedMessages
                self.messages.forEach { message in
                    self.messageHandler?(message)
                }
                print("Loaded saved messages: \(decodedMessages.count)")
                
                // Find createTime of last local message, add 1 sec
                let lastCreateTime: String? = self.messages.last?.createTime
                if let savedConversationId = self.conversationId, let lastCreateTime = lastCreateTime {
                    // Try multiple date formats to handle both stored and API formats
                    var date: Date?
                    
                    // Try with fractional seconds first (API format: "2025-10-30T22:27:19.895000Z")
                    let formatterWithFractional = ISO8601DateFormatter()
                    formatterWithFractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                    if let parsedDate = formatterWithFractional.date(from: lastCreateTime) {
                        date = parsedDate
                    } else {
                        // Try without fractional seconds (stored format: "2025-10-30 22:39:31+00:00")
                        let formatterWithoutFractional = ISO8601DateFormatter()
                        formatterWithoutFractional.formatOptions = [.withInternetDateTime]
                        // Replace space with T for ISO8601 parsing
                        let normalizedTime = lastCreateTime.replacingOccurrences(of: " ", with: "T")
                        if let parsedDate = formatterWithoutFractional.date(from: normalizedTime) {
                            date = parsedDate
                        }
                    }
                    
                    if let parsedDate = date {
                        // Always output in API format (with fractional seconds)
                        let outputFormatter = ISO8601DateFormatter()
                        outputFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                        let plus1sec = parsedDate.addingTimeInterval(1)
                        let newStr = outputFormatter.string(from: plus1sec)
                        // Fetch new messages from API
                        
                        fetchNewMessages(conversationId: savedConversationId, fromCreateDatetime: newStr) { [weak self] result in
                            switch result {
                            case .success(let newMsgs):
                                DispatchQueue.main.async {
                                    // Only append truly new
                                    let existingIds = Set(self?.messages.map { $0.createTime + $0.text } ?? [])
                                    let filteredMsgs = newMsgs.filter { !existingIds.contains($0.createTime + $0.text) }
                                    self?.messages.append(contentsOf: filteredMsgs)
                                    filteredMsgs.forEach { self?.messageHandler?($0) }
                                    print("Appended \(filteredMsgs.count) new messages from API"); self?.saveConversation()
                                }
                            case .failure(let error):
                                print("Failed to fetch new messages: \(error)")
                            }
                        }
                    }else {
                        print("Failed to parse lastCreateTime: \(lastCreateTime)")
                    }
                }
            } catch {
                print("Failed to decode saved messages: \(error)")
                self.messages = []
            }
        } else {
            self.messages = []
        }
        
        // Load saved possible queries
        if let savedConfig = UserDefaults.standard.data(forKey: agentConfigKey) {
            do {
            let decodedConfig = try JSONDecoder().decode(AgentConfiguration.self, from: savedConfig)
            
            self.agentConfig = decodedConfig
            print("Loaded saved possible queries: \(decodedConfig)")
            } catch {
                print("Failed to decode savedConfig: \(error)")
                self.agentConfig = nil
            }
        }
        
    }
    
    private func saveConversation() {
        if let conversationId = conversationId {
            UserDefaults.standard.set(conversationId, forKey: storageKey)
            print("Saved conversation:", conversationId)
        }

        if let lastStart = lastStartConversationTime {
            UserDefaults.standard.set(lastStart.timeIntervalSince1970, forKey: lastStartTimeKey)
            print("Saved last startConversation time: \(lastStart)")
        }
        do {
            let messagesData = try JSONEncoder().encode(messages)
            UserDefaults.standard.set(messagesData, forKey: messagesKey)
            print("Saved messages: \(messages.count)")
        } catch {
            print("Failed to encode messages: \(error)")
        }
        do {
            let agentConfigData = try JSONEncoder().encode(agentConfig)
            UserDefaults.standard.set(agentConfigData, forKey: agentConfigKey)
        } catch {
            print("Failed to encode messages: \(error)")
        }
    }
    
    public func resetConversation() {
        messageTask?.cancel()
        messageTask = nil
        Task {
            await webSocketManager.disconnect()
        }
        conversationId = nil
        messages = []
        lastStartConversationTime = nil
        UserDefaults.standard.removeObject(forKey: storageKey)
        UserDefaults.standard.removeObject(forKey: messagesKey) 
        UserDefaults.standard.removeObject(forKey: agentConfigKey)
        UserDefaults.standard.removeObject(forKey: lastStartTimeKey)
    }
    
    public func updateMessage(index:Int, text:String) {
        let oldMessage = messages[index]
        messages[index] = Message(createTime: oldMessage.createTime, startTime: oldMessage.startTime, endTime: oldMessage.endTime, speaker: oldMessage.speaker, text: text)
        saveConversation()
    }
    
    public func hasActiveConversation() -> Bool {
        return conversationId != nil
    }
    
    public func getConversationId() -> String? {
        return conversationId
    }
    
    public func initializeConversation() async throws -> String {
        if let conversationId = conversationId {
            if useWs {
                connectWebSocket()
            }
            return conversationId
        }
        return try await startConversation()
    }
    
    public func startConversation() async throws -> String {
        let url = URL(string: "\(baseURL)/\(startConversationPath ?? "api/conversations/in-progress/start")")!
        
        let requestBody: [String: Any] = [
            "messages": [],
            "recorded_at": ISO8601DateFormatter().string(from: Date()),
            "data_source_id": "00000196-02d3-6026-a041-ec8564d4a316"
        ]
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "x-api-key")
        if let tenant = tenant {
            request.addValue(tenant, forHTTPHeaderField: "X-Tenant-Id")
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)
        
        let (data, _) = try await URLSession.shared.data(for: request)
        print("Start conversation response: \(data)")

        let response = try JSONDecoder().decode(StartConversationResponse.self, from: data)
        print("Start conversation response: \(response)")

        self.conversationId = response.conversationId
        self.lastStartConversationTime = Date() // Update last startConversation time
        saveConversation()
        if useWs {
            connectWebSocket()
        }
        let welcomeImage: String? = if response.agentHasWelcomeImage ?? false {
            "\(baseURL)/api/genagent/agents/configs/\(response.agentId)/welcome-image"
        } else {
            nil
        }
        self.agentConfig = AgentConfiguration(agentId: response.agentId, conversationId: response.conversationId, agentWelcomeMessage: response.agentWelcomeMessage, agentWelcomeTitle: response.agentWelcomeTitle, agentWelcomeImage: welcomeImage, agentPossibleQueries: response.agentPossibleQueries, agentThinkingPhrases: response.agentThinkingPhrases)
        do{
            let agentConfigData = try JSONEncoder().encode(agentConfig)
            UserDefaults.standard.set(agentConfigData, forKey: agentConfigKey)
        }catch{
            print(error)
        }

        
//        // Create welcome message object
//        if let welcomeMessageText = response.agentWelcomeMessage {
//
//            
////            // Also send as regular message for backward compatibility
////            if let handler = messageHandler {
////                let now = Int64(Date().timeIntervalSince1970 * 1000)
////                let message = Message(
////                    createTime: ISO8601DateFormatter().string(from: Date()),
////                    startTime: Double(now) / 1000,
////                    endTime: Double(now) / 1000 + 0.01,
////                    speaker: "agent",
////                    text: welcomeMessageText
////                )
////                handler(message)
////            }
//        }
        
        return response.conversationId
    }
    
    public func sendMessage(_ message: String, extraMetadata: [String: Any]? = nil) async throws {
        guard let conversationId = conversationId else {
            throw NSError(domain: "ChatService", code: -1, userInfo: [NSLocalizedDescriptionKey: "Conversation not started"])
        }
        let now = Date()
        let startTime: Double
        if let lastStart = lastStartConversationTime {
            startTime = now.timeIntervalSince(lastStart)
        } else {
            startTime = 0.0
        }
        let chatMessage = Message(
            createTime: ISO8601DateFormatter().string(from: now),
            startTime: startTime,
            endTime: startTime + 0.01,
            speaker: "customer",
            text: message
        )
        if !useWs {
            // Add the sent message to messages array
            // messages.append(chatMessage)
            // saveConversation()
            messageHandler?(chatMessage)

        }
        
        let url = URL(string: "\(baseURL)/\(updateConversationPath ?? "api/conversations/in-progress/update")/\(conversationId)")!
        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "x-api-key")
        if let tenant = tenant {
            request.addValue(tenant, forHTTPHeaderField: "X-Tenant-Id")
        }
        
        // Merge base metadata with extra metadata
        var finalMetadata: [String: Any] = self.metadata.getMetadata()
        if let customerId = customerId { finalMetadata["customerId"] = customerId }
        if let extraMetadata = extraMetadata {
            // Convert Any values to String for consistency with existing metadata structure
            for (key, value) in extraMetadata {
                finalMetadata[key] = value
            }
        }
        
        let body = ["messages": [chatMessage.toJSON()], "metadata": finalMetadata] as [String : Any]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw NSError(domain: "ChatService", code: -1, userInfo: [NSLocalizedDescriptionKey: "Failed to send message"])
        }
        
        // If not using WebSocket, try to retrieve the response message from the update conversation response
        if !useWs {
            // Add the sent message to messages array
            // messages.append(chatMessage)
            // saveConversation()
            
            do {
                let responseData = try JSONSerialization.jsonObject(with: data) as? [String: Any]
                
                if let responseMessages = responseData?["messages"] as? [[String: Any]] {

                    // Look for the latest agent message in the response
                    for messageData in responseMessages.reversed() {
                        if let speaker = messageData["speaker"] as? String, speaker == "agent",
                           let text = messageData["text"] as? String,
                           let createTime = messageData["create_time"] as? String,
                           let startTime = messageData["start_time"] as? Double,
                           let endTime = messageData["end_time"] as? Double {
                            
                            let agentMessage = Message(
                                createTime: createTime,
                                startTime: startTime,
                                endTime: endTime,
                                speaker: speaker,
                                text: text
                            )
                            
                            // Only process if this is a new message we haven't seen before
                            if !messages.contains(where: { $0.createTime == createTime && $0.text == text }) {
                                messageHandler?(agentMessage)
                            }
                            break
                        }
                    }
                }
            } catch {
                print("Failed to parse update conversation response: \(error)")
            }
        }
    }
    
    public func connectWebSocket() {
        guard useWs else {
            print("WebSocket: WebSocket is disabled")
            return
        }
        
        guard let conversationId = conversationId else {
            print("WebSocket: No conversation ID available")
            return
        }
        
        var urlString = "\(baseURL.replacingOccurrences(of: "http", with: "ws"))/api/conversations/ws/\(conversationId)?api_key=\(apiKey)&lang=en&topics=message"
        if let tenant = tenant, let encodedTenant = tenant.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) {
            urlString += "&X-Tenant-Id=\(encodedTenant)"
        }
        guard let url = URL(string: urlString) else {
            print("WebSocket: Invalid URL: \(urlString)")
            return
        }
        
        print("WebSocket: Connecting to URL: \(urlString)")
        messageTask?.cancel()
        
        var headers: [String: String] = [:]
        if let tenant = tenant {
            headers["X-Tenant-Id"] = tenant
        }
        
        messageTask = Task {
            await webSocketManager.connect(url: url, headers: headers)
            
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
        if useWs {
            Task {
                await webSocketManager.disconnect()
            }
        }
    }
    
    public func getMessages() -> [Message] {
        return messages
    }
    
    // Fetch new messages from server
    private func fetchNewMessages(conversationId: String, fromCreateDatetime: String, completion: @escaping (Result<[Message], Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)/api/conversations/\(conversationId)?from_create_datetime_messages=\(fromCreateDatetime)") else {
            completion(.failure(NSError(domain: "ChatService", code: 400, userInfo: [NSLocalizedDescriptionKey: "Invalid URL"])))
            return
        }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.addValue(apiKey, forHTTPHeaderField: "x-api-key")
        if let tenant = tenant {
            request.addValue(tenant, forHTTPHeaderField: "X-Tenant-Id")
        }
        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let data = data else {
                completion(.failure(NSError(domain: "ChatService", code: 500, userInfo: [NSLocalizedDescriptionKey: "No data"])))
                return
            }
            do {
                let decoder = JSONDecoder()
                // Make decoder more lenient with unknown keys
                let conversationResp = try decoder.decode(ConversationResponse.self, from: data)
                // Use messages array directly if available, otherwise fallback to transcription string
                if let messages = conversationResp.messages {
                    completion(.success(messages))
                } else if let transcription = conversationResp.transcription,
                          let transcriptionData = transcription.data(using: .utf8) {
                    // Fallback: parse transcription string for backward compatibility
                    let newMessages = try decoder.decode([Message].self, from: transcriptionData)
                    completion(.success(newMessages))
                } else {
                    // No messages found
                    completion(.success([]))
                }
            } catch {
                // Log the actual error for debugging
                if let jsonString = String(data: data, encoding: .utf8) {
                    print("Failed to decode ConversationResponse. Error: \(error)")
                    print("Response data: \(jsonString.prefix(500))")
                }
                completion(.failure(error))
            }
        }
        task.resume()
    }
} 

//
//  GenassistChatPreview.swift
//  GenassistChatIOS
//
//  Created by Krist V on 24.5.25.
//

import SwiftUI

// Mock service for preview
class MockChatService: ChatService {
    private var messageHandler: ((Message) -> Void)?
    private var mockPossibleQueries = [
        "How can I reset my password?",
        "What are your business hours?",
        "How do I contact support?"
    ]
    
    override func setMessageHandler(_ handler: @escaping (Message) -> Void) {
        self.messageHandler = handler
    }
    
    override func getPossibleQueries() -> [String] {
        return mockPossibleQueries
    }
    
    override func startConversation() async throws -> String {
        // Simulate network delay
        try await Task.sleep(nanoseconds: 1_000_000_000)
        
        // Simulate welcome message
        if let handler = messageHandler {
            let now = Int64(Date().timeIntervalSince1970 * 1000)
            let welcomeMessage = Message(
                createTime: ISO8601DateFormatter().string(from: Date()),
                startTime: Double(now) / 1000,
                endTime: Double(now) / 1000 + 0.01,
                speaker: "agent",
                text: "Hello! How can I help you today?"
            )
            handler(welcomeMessage)
        }
        
        return "mock-conversation-id"
    }
    
    override func sendMessage(_ message: String, extraMetadata: [String: Any]? = nil) async throws {
        // Simulate network delay
        try await Task.sleep(nanoseconds: 500_000_000)
        
        // Simulate agent response
        if let handler = messageHandler {
            let now = Int64(Date().timeIntervalSince1970 * 1000)
            let response = Message(
                createTime: ISO8601DateFormatter().string(from: Date()),
                startTime: Double(now) / 1000,
                endTime: Double(now) / 1000 + 0.01,
                speaker: "agent",
                text: "This is a mock response to: \(message)"
            )
            handler(response)
        }
    }
    
    override func connectWebSocket() {
        // WebSocket connection is handled automatically in the mock service
    }
    
    override func disconnect() {
        // Cleanup is handled automatically in the mock service
    }
}

struct GenassistChatPreview: PreviewProvider {
    static var previews: some View {
        Group {
            // Light mode preview
            GenassistChat(
                baseURL: "http://localhost:8000",
                apiKey: "PREVIEW_PLACEHOLDER", // Never commit real API keys
                metadata: ChatMetadata(
                    userInfo: [
                        "name": "Preview User",
                        "email": "preview@example.com"
                    ],
                    additionalData: [
                        "environment": "preview",
                        "version": "1.0.0"
                    ]
                ),

            )
            .previewDisplayName("Light Mode")
            
            // Dark mode preview
            GenassistChat(
                baseURL: "http://localhost:8000",
                apiKey: "PREVIEW_PLACEHOLDER", // Never commit real API keys
                metadata: ChatMetadata(
                    userInfo: [
                        "name": "Preview User",
                        "email": "preview@example.com"
                    ],
                    additionalData: [
                        "environment": "preview",
                        "version": "1.0.0"
                    ]
                ),

            )
            .preferredColorScheme(.dark)
            .previewDisplayName("Dark Mode")
            
            // Voice disabled preview
            GenassistChat(
                baseURL: "http://localhost:8000",
                apiKey: "PREVIEW_PLACEHOLDER", // Never commit real API keys
                metadata: ChatMetadata(
                    userInfo: [
                        "name": "Preview User",
                        "email": "preview@example.com"
                    ],
                    additionalData: [
                        "environment": "preview",
                        "version": "1.0.0"
                    ]
                ),

            )
            .previewDisplayName("Voice Disabled")
        }
    }
}

//
//  GenassistChat.swift
//  GenassistChatIOS
//
//  Created by Krist V on 24.5.25.
//
import SwiftUI

@MainActor
public struct GenassistChat: View {
    @State private var messages: [ChatMessage] = []
    @State private var newMessage: String = ""
    @State private var isLoading: Bool = false
    @State private var error: Error?
    @State private var showResetConfirm: Bool = false
    @State private var showMenu: Bool = false
    @State private var isPlayingAudio: Bool = false
    @State private var connectionState: ConnectionState = .disconnected
    @State private var possibleQueries: [String] = []
    
    let configuration: ChatConfiguration
    let chatService: ChatService
    let headerTitle: String
    let placeholder: String
    
    public enum ConnectionState {
        case connecting
        case connected
        case disconnected
    }
    
    public init(
        baseURL: String,
        apiKey: String,
        metadata: ChatMetadata,
        configuration: ChatConfiguration = ChatConfiguration(),
        headerTitle: String = "Genassist",
        placeholder: String = "Ask a question"
    ) {
        self.configuration = configuration
        self.chatService = ChatService(baseURL: baseURL, apiKey: apiKey, metadata: metadata)
        self.headerTitle = headerTitle
        self.placeholder = placeholder
    }
    
    public var body: some View {
        mainContainer
            .overlay(loadingOverlay)
            .alert("Error", isPresented: .constant(error != nil)) {
                Button("OK") { error = nil }
            } message: {
                Text(error?.localizedDescription ?? "An unknown error occurred")
            }
            .alert("Reset Conversation", isPresented: $showResetConfirm) {
                Button("Cancel", role: .cancel) { showResetConfirm = false }
                Button("Reset", role: .destructive) {
                    Task {
                        await resetConversation()
                        showResetConfirm = false
                    }
                }
            } message: {
                Text("This will clear the current conversation history and start a new conversation. Are you sure?")
            }
            .task {
                await initializeConversation()
            }
            .onDisappear {
                chatService.disconnect()
            }
    }
    
    private var mainContainer: some View {
        VStack(spacing: 0) {
            headerView
            chatContainer
            if !possibleQueries.isEmpty && !messages.contains(where: { $0.isUser }) {
                possibleQueriesView
            }
            inputView
        }
    }
    
    private var loadingOverlay: some View {
        Group {
            if isLoading {
                ProgressView()
                    .scaleEffect(1.5)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color.black.opacity(0.2))
            }
        }
    }
    
    private var chatContainer: some View {
        ScrollView {
            LazyVStack(spacing: configuration.spacing) {
                ForEach(messages) { message in
                    MessageBubble(
                        message: message,
                        configuration: configuration
                    )
                }
            }
            .padding()
        }
        .background(configuration.backgroundColor)
    }
    
    private var headerView: some View {
        HStack {
            HStack(spacing: 10) {
                Image(systemName: "bubble.left.and.bubble.right.fill")
                    .resizable()
                    .frame(width: 28, height: 28)
                    .foregroundColor(.white)
                
                VStack(alignment: .leading) {
                    Text(headerTitle)
                        .font(.headline)
                        .foregroundColor(.white)
                    Text("Support")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.8))
                }
            }
            
            Spacer()
            
            Button(action: { showMenu.toggle() }) {
                Image(systemName: "ellipsis")
                    .foregroundColor(.white)
                    .frame(width: 32, height: 32)
            }
            .popover(isPresented: $showMenu) {
                Button(action: { showResetConfirm = true }) {
                    Label("Reset conversation", systemImage: "arrow.counterclockwise")
                }
                .padding()
            }
        }
        .padding()
        .background(configuration.userBubbleColor)
    }
    
    private var possibleQueriesView: some View {
        VStack(spacing: 8) {
            ForEach(possibleQueries, id: \.self) { query in
                Button(action: {
                    Task {
                        await sendMessage(query)
                    }
                }) {
                    Text(query)
                        .frame(maxWidth: 240, alignment: .leading)
                        .padding()
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(6)
                }
                .disabled(isLoading)
            }
        }
        .padding(.horizontal, 28)
        .padding(.vertical, 8)
    }
    
    private var inputView: some View {
        HStack(spacing: 8) {
            HStack {
                Button(action: {}) {
                    Image(systemName: "paperclip")
                        .foregroundColor(.gray)
                }
                
                TextField(placeholder, text: $newMessage)
                    .textFieldStyle(.plain)
                    .disabled(connectionState != .connected)
                
                Button(action: {
                    Task {
                        await sendMessage(newMessage)
                    }
                }) {
                    Image(systemName: "arrow.up.circle.fill")
                        .resizable()
                        .frame(width: 32, height: 32)
                        .foregroundColor(configuration.sendButtonColor)
                }
                .disabled(newMessage.trimmed.isBlank || connectionState != .connected)
            }
            .padding()
            .background(Color.gray.opacity(0.1))
            .cornerRadius(8)
        }
        .padding()
        .background(Color.gray.opacity(0.05))
    }
    
    private func initializeConversation() async {
        isLoading = true
        connectionState = .connecting
        
        do {
            chatService.setMessageHandler { message in
                let chatMessage = ChatMessage(
                    content: message.text,
                    isUser: message.speaker == "customer",
                    timestamp: ISO8601DateFormatter().date(from: message.createTime) ?? Date()
                )
                messages.append(chatMessage)
            }
            
            let convId = try await chatService.initializeConversation()
            possibleQueries = chatService.getPossibleQueries()
            connectionState = .connected
        } catch {
            self.error = error
            connectionState = .disconnected
        }
        
        isLoading = false
    }
    
    private func resetConversation() async {
        isLoading = true
        connectionState = .connecting
        messages = []
        possibleQueries = []
        
        do {
            chatService.resetConversation()
            let convId = try await chatService.startConversation()
            possibleQueries = chatService.getPossibleQueries()
            connectionState = .connected
        } catch {
            self.error = error
            connectionState = .disconnected
        }
        
        isLoading = false
    }
    
    private func sendMessage(_ text: String) async {
        let trimmedMessage = text.trimmed
        guard !trimmedMessage.isBlank else { return }
        
//        let userMessage = ChatMessage(content: trimmedMessage, isUser: true)
//        messages.append(userMessage)
        newMessage = ""
        
        do {
            try await chatService.sendMessage(trimmedMessage)
        } catch {
            self.error = error
        }
    }
}


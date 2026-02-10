//
//  GenassistChat.swift
//  GenassistChatIOS
//
//  Created by Krist V on 24.5.25.
//
import SwiftUI
import Foundation
import AVFoundation

@MainActor
public struct GenassistChat: View {
    @State private var messages: [ChatMessage] = []
    @State private var newMessage: String = ""
    @State private var isLoading: Bool = false
    @State private var waitingForResponse: Bool = false
    @State private var error: Error?
    @State private var showResetConfirm: Bool = false
    @State private var showMenu: Bool = false
    @State private var isPlayingAudio: Bool = false
    @State private var isRecording: Bool = false
    @State private var connectionState: ConnectionState = .disconnected
    @State private var possibleQueries: [String] = []
    @State private var thinkingPhrases: [String] = []
    @State private var welcomeScreenData: WelcomeScreenData?
    @State private var lastUserMessageWasSpeech: Bool = false
    @State private var showPermissionAlert: Bool = false
    @StateObject private var viewModel = SpeechRecognizerViewModel()
    @StateObject private var textToSpeechManager = TextToSpeechManager()
    private let soundManager = SoundManager()
    @Environment(\.openURL) private var openURL
    
    let configuration: ChatConfiguration
    let chatService: ChatService
    let headerTitle: String
    let headerSubtitle: String
    
    let placeholder: String
    let headerLogo: AnyView?
    let onDynamicItemTap: ((DynamicChatItem) -> Void)?
    let tenant: String?
    let customerId: String?
    
    public enum ConnectionState {
        case connecting
        case connected
        case disconnected
    }
    
    public init(
        baseURL: String,
        apiKey: String,
        startConversationPath: String? = nil,
        updateConversationPath: String? = nil,
        useWs: Bool = true,
        metadata: ChatMetadata,
        tenant: String? = nil,
        customerId: String? = nil,
        configuration: ChatConfiguration = ChatConfiguration(),
        headerTitle: String = "Genassist",
        headerSubtitle: String = "",
        placeholder: String = "Ask a question",
        headerLogo: AnyView? = nil,
        onDynamicItemTap: ((DynamicChatItem) -> Void)? = nil,
    ) {
        self.configuration = configuration
        self.chatService = ChatService(baseURL: baseURL, apiKey: apiKey, metadata: metadata, startConversationPath: startConversationPath, updateConversationPath: updateConversationPath, useWs: useWs, tenant: tenant, customerId: customerId)
        self.headerTitle = headerTitle
        self.headerSubtitle = headerSubtitle
        self.placeholder = placeholder
        self.headerLogo = headerLogo
        self.onDynamicItemTap = onDynamicItemTap
        self.tenant = tenant
        self.customerId = customerId

    }
    
    
    public var body: some View {
        mainContainer
        //.overlay(loadingOverlay)
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
            .alert("Voice Permission Required", isPresented: $showPermissionAlert) {
                Button("Open Settings") {
                    if let settingsUrl = URL(string: "App-Prefs:root=Privacy&path=MICROPHONE") {
                        openURL(settingsUrl)
                    }
                }
                Button("Cancel", role: .cancel) { showPermissionAlert = false }
            } message: {
                Text(viewModel.permissionError ?? "Voice permissions are required to use speech-to-text functionality.")
            }
            .task {
                await initializeConversation()
            }
            .onDisappear {
                chatService.disconnect()
            }
        //            .onReceive(NotificationCenter.default.publisher(for: .scenePhase)) { phase in
        //                // Check permissions when app becomes active (e.g., returning from Settings)
        //                if phase == .active && configuration.useVoice {
        //                    Task {
        //                        await viewModel.checkPermissions()
        //                    }
        //                }
        //            }
    }
    
    private var mainContainer: some View {
        VStack(spacing: 0) {
            headerView
            chatContainer
            inputView
        }.background(configuration.backgroundColor)
        
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
    private var conversationSection: some View {
        ForEach(Array(messages.enumerated()), id: \.element.id) { index, message in
            MessageBubble(
                message: message,
                configuration: configuration,
                isLastMessage: index == messages.count - 1 && !message.isUser,
                onDynamicItemTap: { item in
                    onDynamicItemTap?(item)
                    if message.id == messages.last?.id {
                        Task {
                            await sendMessage(item.name)
                        }
                    }
                    
                },
                onOptionTap: { option in
                    if message.id == messages.last?.id {
                        Task {
                            await sendMessage(option)
                        }
                    }
                },
                onFeedbackTap: { isPositive in
                    handleFeedback(isPositive: isPositive, messageId: message.id)
                },
                onScheduleConfirm: { scheduleItem in
                    if message.id == messages.last?.id {
                        Task {
                            // Encode ScheduleItem to JSON for metadata
                            let scheduleStringified: String = {
                                if let jsonData = try? JSONEncoder().encode(scheduleItem),
                                   let jsonString = try? String(data: jsonData, encoding: .utf8) {
                                    return jsonString
                                }
                                return "{}"
                            }()
                            
                            await sendMessage(
                                //"Schedule confirmed with \(scheduleItem.restaurants.count) restaurants",
                                "Confirm Schedule",
                                extraMetadata: ["confirmSchedule": scheduleStringified]
                            )
                        }
                    }
                },
                onMessageUpdate: { updatedContent in
                    if let messageIndex = messages.firstIndex(where: { $0.id == message.id }) {
//                        messages[messageIndex] = ChatMessage(
//                            id: message.id,
//                            content: updatedContent,
//                            isUser: message.isUser,
//                            timestamp: message.timestamp
//                        )
                        chatService.updateMessage(index:messageIndex, text:updatedContent)

                    }
                }
            )
            .id(message.id)
        }
    }
    

    
    private var chatContainer: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: configuration.spacing) {
                    // Welcome Message
                    if let welcomeScreenData = welcomeScreenData {
                        WelcomeScreenView(
                            welcomeScreenData: welcomeScreenData,
                            configuration: configuration,
                            onQueryTap: { query in
                                Task {
                                    await sendMessage(query)
                                }
                            }
                        )
//                        .padding(.horizontal)
                    }
                    conversationSection
                    
                    if waitingForResponse {
                        TypingIndicator(configuration: configuration, thinkingPhrases: thinkingPhrases)
                            .id(-1)
                    }
                }
                .padding()
            }
            .onChange(of: messages.count) { _ in
                if let lastMessage = messages.last {
                    withAnimation {
                        proxy.scrollTo(lastMessage.id, anchor: .bottom)
                    }
                }
            }
            .onChange(of: waitingForResponse){ _ in
                if waitingForResponse {
                    // Use a slight delay to ensure the loading view is rendered
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                        withAnimation {
                            proxy.scrollTo(-1, anchor: .bottom)
                        }
                    }
                }
            }
        }
    }
    
    private var headerView: some View {
        HStack {
            HStack(spacing: 10) {
                if headerLogo == nil {
                    Image(systemName: "bubble.left.and.bubble.right.fill")
                        .resizable()
                        .frame(width: 28, height: 28)
                        .foregroundColor(configuration.header.primaryTextColor)
                }else {
                    headerLogo
                }
              
                
                VStack(alignment: .leading) {
                    Text(headerTitle)
                        .font(configuration.header.titleFont)
                        .foregroundColor(configuration.header.primaryTextColor)
                    if headerSubtitle != "" {Text(headerSubtitle)
                            .font(configuration.header.subtitleFont)
                        .foregroundColor(configuration.header.primaryTextColor.opacity(0.8))}
                }
            }
            
            Spacer()
            
            // Text-to-speech indicator
            if configuration.useVoice && textToSpeechManager.isSpeaking {
                HStack(spacing: 4) {
                    Image(systemName: "speaker.wave.2.fill")
                        .foregroundColor(.green)
                        .font(.caption)
                    Text("Speaking")
                        .font(.caption)
                        .foregroundColor(.green)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.green.opacity(0.1))
                .cornerRadius(8)
            }
            
            // Voice permission warning
            if configuration.useVoice && !viewModel.hasPermissions && viewModel.permissionError != nil {
                HStack(spacing: 4) {
                    Image(systemName: "mic.slash")
                        .foregroundColor(.orange)
                        .font(.caption)
                    Text("Voice Disabled")
                        .font(.caption)
                        .foregroundColor(.orange)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.orange.opacity(0.1))
                .cornerRadius(8)
            }
            
            Menu {
                if configuration.useVoice && textToSpeechManager.isSpeaking {
                    Button(action: { textToSpeechManager.stop() }) {
                        Label("Stop speaking", systemImage: "stop.fill")
                    }
                    Divider()
                }
                Button(role: .destructive, action: { showResetConfirm = true }) {
                    Label("Reset conversation", systemImage: "arrow.counterclockwise")
                }
            } label: {
                Image(systemName: "ellipsis")
                    .foregroundColor(.primary)
                    .frame(width: 32, height: 32)
            }
        }
        .padding()
        .background(configuration.header.backgroundColor)
    }
    

    
    private var inputView: some View {
        HStack(spacing: 8) {
            HStack {
                // Button(action: {}) {
                //     Image(systemName: "paperclip")
                //         .foregroundColor(Color(.systemGray))
                //         .frame(width: 24, height: 24)
                // }
                
                TextField(placeholder, text: $newMessage)
                    .textFieldStyle(.plain)
                    .font(configuration.inputField.textFont)
                    .foregroundColor(configuration.inputField.textColor)
                    .padding(.horizontal, 10)
                    .disabled(connectionState != .connected)
            }
            .padding(.horizontal, 15)
            .padding(.vertical, 0)
            .frame(height: 48)
            .background(Color.white)
            .cornerRadius(configuration.inputField.cornerRadius)
            .shadow(color: Color.black.opacity(0.05), radius: 1, x: 0, y: 1)
            
            Button(action: {
                if !newMessage.trimmed.isBlank {
                    Task {
                        await sendMessage(newMessage)
                    }
                } else if configuration.useVoice {
                    // If voice is enabled and no text, start recording
                    Task {
                        // Check permissions first
                        await viewModel.checkPermissions()
                        if viewModel.hasPermissions {
                            toggleRecording(start: true)
                        } else {
                            // Show permission alert
                            showPermissionAlert = true
                        }
                    }
                }
            }) {
                
                Image(systemName: getButtonIcon())
                    .resizable()
                    .scaledToFit()
                    .foregroundColor(.white)                    
                    .frame(width: configuration.inputField.iconSize, height: configuration.inputField.iconSize)
            }
            .disabled(connectionState != .connected || (newMessage.trimmed.isBlank && !configuration.useVoice) || (newMessage.trimmed.isBlank && configuration.useVoice && !viewModel.hasPermissions))
            .frame(width: 42, height: 42)
            
            .padding(3)
            .background(
                ZStack {
                    RoundedRectangle(cornerRadius: configuration.inputField.cornerRadius)
                        .foregroundColor(isRecording ? configuration.inputField.sendButtonColor.opacity(0.3) : configuration.inputField.sendButtonColor)
                  
                    
                }
              )
            .simultaneousGesture(
                        LongPressGesture(minimumDuration: 0.2)
                            .onEnded { _ in
                                if configuration.useVoice {

                                    if newMessage.trimmed.isBlank {
                                        Task {
                                            // Check permissions first
                                            await viewModel.checkPermissions()
                                            if viewModel.hasPermissions {
                                                toggleRecording(start: true)
                                            } else {
                                                // Show permission alert
                                                showPermissionAlert = true
                                            }
                                        }
                                    }
                                }
                         
                    }
                
            )
            .simultaneousGesture(
               
                        DragGesture(minimumDistance: 0)
                            .onChanged { _ in }
                            .onEnded { _ in
                                if configuration.useVoice {

                                    if isRecording {
                                        toggleRecording(start:false)
                                    }
                                }
                            }
                
                
            )
        }
        .padding(configuration.inputField.padding)
        .onChange(of: viewModel.transcript) { newTranscript in
                   // Only update the field if we're recording and voice is enabled
                    if isRecording && configuration.useVoice {
                       newMessage = newTranscript
                   }
               }
    }
    
    private func initializeConversation() async {
        connectionState = .connecting
        isLoading = true
        do {
            chatService.setMessageHandler { message in
                print(message)
                let chatMessage = ChatMessage(
                    content: message.text,
                    isUser: message.speaker == "customer",
                    timestamp: ISO8601DateFormatter().date(from: message.createTime) ?? Date()
                )
                messages.append(chatMessage)

                if !chatMessage.isUser {
                    waitingForResponse = false
                    // If the last user message was sent via speech and text-to-speech is enabled, speak the response
                    if self.lastUserMessageWasSpeech && self.configuration.enableTextToSpeech && self.configuration.useVoice {
                        let (before, items, after) = parseInteractiveContent(message.text)
                        let textToSpeak = before + (items?.map { $0.name ?? "" }.joined(separator: ", ") ?? "") + after
                        self.textToSpeechManager.speak(
                            textToSpeak,
                            rate: self.configuration.speechRate,
                            volume: self.configuration.speechVolume
                        )
                    }
                }
//                if chatMessage.isUser {
//                    isLoading = true
//                }
            }
            // Load saved messages
            let savedMessages = chatService.getMessages()
            let chatMessages = savedMessages.map { message in
                ChatMessage(
                    content: message.text,
                    isUser: message.speaker == "customer",
                    timestamp: ISO8601DateFormatter().date(from: message.createTime) ?? Date()
                )
            }
            messages = chatMessages

            
            let convId = try await chatService.initializeConversation()
            possibleQueries = chatService.getPossibleQueries()
            thinkingPhrases = chatService.getThinkingPhrases()
            welcomeScreenData = chatService.getWelcomeMessage()
            connectionState = .connected
            isLoading = false
        } catch {
            self.error = error
            connectionState = .disconnected
            isLoading = false
        }
    }
    
    private func resetConversation() async {
        isLoading = true
        waitingForResponse = false
        connectionState = .connecting
        messages = []
        possibleQueries = []
        thinkingPhrases = []
        welcomeScreenData = nil
        
        do {
            chatService.resetConversation()
            let convId = try await chatService.startConversation()
            possibleQueries = chatService.getPossibleQueries()
            thinkingPhrases = chatService.getThinkingPhrases()
            welcomeScreenData = chatService.getWelcomeMessage()
            connectionState = .connected
        } catch {
            self.error = error
            connectionState = .disconnected
        }
        
        isLoading = false
    }
    
    private func sendMessage(_ text: String, extraMetadata: [String: Any]? = nil, wasSentViaSpeech: Bool = false) async {
        let trimmedMessage = text.trimmed
        guard !trimmedMessage.isBlank else { return }
        
        // Track if this message was sent via speech-to-text
        lastUserMessageWasSpeech = wasSentViaSpeech
        
        newMessage = ""
//        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
//            isLoading = true
//        }
        
        // Set waitingForResponse to true after 1 second
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            waitingForResponse = true
        }

        do {
            try await chatService.sendMessage(trimmedMessage,extraMetadata:extraMetadata)
        } catch {
            //self.error = error
        }

    }
    
    private func getButtonIcon() -> String {
        if isRecording {
            return "mic"
        }
        
        if newMessage.trimmed.isBlank && configuration.useVoice {
            // Show different icon based on permission status
            if viewModel.hasPermissions {
                return "mic"
            } else {
                return "mic.slash" // Show disabled mic icon
            }
        }
        
        return "arrow.up"
    }
    
    func toggleRecording(start: Bool = false) {
        guard configuration.useVoice else { return }
        
        if start {
            isRecording = true
            Task { 
                await viewModel.start()
                
                // Check if there was a permission error
                if viewModel.permissionError != nil {
                    await MainActor.run {
                        isRecording = false
                        showPermissionAlert = true
                    }
                }
            }
            self.textToSpeechManager.stop()
            soundManager.playRecordingStartSound()
        } else {
            isRecording = false
            viewModel.stop()
            soundManager.playRecordingStopSound()
            
            // If there's a transcript, send it as a speech-to-text message
            if !viewModel.transcript.trimmed.isBlank {
                Task {
                    await sendMessage(viewModel.transcript, wasSentViaSpeech: true)
                }
            }
        }
    }
    
    private func handleFeedback(isPositive: Bool, messageId: UUID) {
        // Handle feedback - you can customize this based on your needs
        // For now, we'll just print the feedback
        print("Feedback received: \(isPositive ? "thumbs up" : "thumbs down") for message \(messageId)")
        if !isPositive {
            Task {
                await sendMessage("Not a good response!")
            }
        }
        // You can add additional logic here such as:
        // - Sending feedback to your backend
        // - Storing feedback locally
        // - Updating UI state to show feedback was received
    }
    
}



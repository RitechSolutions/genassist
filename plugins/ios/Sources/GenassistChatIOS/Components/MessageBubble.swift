import SwiftUI

public enum FeedbackState {
    case none
    case thumbsUp
    case thumbsDown
}

public struct MessageBubble: View {
    let message: ChatMessage
    let configuration: ChatConfiguration
    let onDynamicItemTap: ((DynamicChatItem) -> Void)?
    let onOptionTap: ((String) -> Void)?
    let onItemSlotTap: ((DynamicChatItem,String) -> Void)?
    let onScheduleConfirm: ((ScheduleItem) -> Void)?
    let onMessageUpdate: ((String) -> Void)?

    let isLastMessage: Bool
    let onFeedbackTap: ((Bool) -> Void)?
    
    @State private var feedbackGiven: FeedbackState = .none
    
    private let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return formatter
    }()
    
    public init(message: ChatMessage, configuration: ChatConfiguration, isLastMessage: Bool = false, onDynamicItemTap: ((DynamicChatItem) -> Void)? = nil, onItemSlotTap: ((DynamicChatItem,String) -> Void)? = nil, onOptionTap: ((String) -> Void)? = nil, onFeedbackTap: ((Bool) -> Void)? = nil,    onScheduleConfirm: ((ScheduleItem) -> Void)? = nil, onMessageUpdate: ((String) -> Void)? = nil) {
        self.message = message
        self.configuration = configuration
        self.isLastMessage = isLastMessage
        self.onDynamicItemTap = onDynamicItemTap
        self.onOptionTap = onOptionTap
        self.onFeedbackTap = onFeedbackTap
        self.onItemSlotTap = onItemSlotTap
        self.onScheduleConfirm = onScheduleConfirm
        self.onMessageUpdate = onMessageUpdate
    }
    
    public var body: some View {
        VStack(alignment: message.isUser ? .trailing : .leading, spacing: configuration.timestamp.spacing) {
            // Timestamp and sender label
            HStack(spacing: configuration.timestamp.spacing) {
                if message.isUser {Text(dateFormatter.string(from: message.timestamp))
                        .font(configuration.timestamp.timeFont)
                    .foregroundColor(configuration.timestamp.timeColor)}
                
                Text(message.isUser ? "You" : "Virtual Angel")
                    .font(configuration.timestamp.senderFont)
                    .foregroundColor(configuration.timestamp.senderColor)
                if !message.isUser {Text(dateFormatter.string(from: message.timestamp))
                        .font(configuration.timestamp.timeFont)
                    .foregroundColor(configuration.timestamp.timeColor)}
            }
            .frame(maxWidth: .infinity, alignment: message.isUser ? .trailing : .leading)
            
            // Message bubble
            HStack {
                if message.isUser {
                    Spacer()
                }
                
                InteractiveChatItem(messageText: message.content, configuration: configuration, isUser: message.isUser, onDynamicItemTap: onDynamicItemTap, onOptionTap: onOptionTap, onItemSlotTap: onItemSlotTap, onScheduleConfirm: onScheduleConfirm,onMessageUpdate: onMessageUpdate, isLastMessage: isLastMessage)
                    .padding(.horizontal, message.isUser ? configuration.senderMessage.padding : configuration.receivedMessage.padding)
                    .padding(.vertical, message.isUser ? configuration.senderMessage.padding/2 : configuration.receivedMessage.padding/2)
                    .background(message.isUser ? configuration.senderMessage.bubbleColor : configuration.receivedMessage.bubbleColor)
                    .foregroundColor(message.isUser ? configuration.senderMessage.textColor : configuration.receivedMessage.textColor)
                    .cornerRadius(message.isUser ? configuration.senderMessage.cornerRadius : configuration.receivedMessage.cornerRadius)
                
                if !message.isUser {
                    Spacer()
                }
            }
            
            // Feedback buttons for the last assistant message
            if !message.isUser && isLastMessage {
                HStack(spacing: 12) {
                    
                    Button(action: {
                        if feedbackGiven == .none {
                            feedbackGiven = .thumbsUp
                            onFeedbackTap?(true)
                        }
                    }) {
                        Image(systemName: "hand.thumbsup")
                            .font(.system(size: 16))
                            .foregroundColor(feedbackGiven == .thumbsUp ? .blue : .gray)
                    }
                    .buttonStyle(PlainButtonStyle())
                    .disabled(feedbackGiven != .none)
                    
                    Button(action: {
                        if feedbackGiven == .none {
                            feedbackGiven = .thumbsDown
                            onFeedbackTap?(false)
                        }
                    }) {
                        Image(systemName: "hand.thumbsdown")
                            .font(.system(size: 16))
                            .foregroundColor(feedbackGiven == .thumbsDown ? .red : .gray)
                    }
                    .buttonStyle(PlainButtonStyle())
                    .disabled(feedbackGiven != .none)
                    Spacer()

                }
                .padding(.top, 8)
            }
        }
    }
} 

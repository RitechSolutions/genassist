import SwiftUI

public struct MessageBubble: View {
    let message: ChatMessage
    let configuration: ChatConfiguration
    
    public init(message: ChatMessage, configuration: ChatConfiguration) {
        self.message = message
        self.configuration = configuration
    }
    
    public var body: some View {
        HStack {
            if message.isUser {
                Spacer()
            }
            
            Text(message.content)
                .padding(configuration.bubblePadding)
                .background(message.isUser ? configuration.userBubbleColor : configuration.bubbleColor)
                .foregroundColor(message.isUser ? configuration.userTextColor : configuration.textColor)
                .cornerRadius(configuration.cornerRadius)
            
            if !message.isUser {
                Spacer()
            }
        }
    }
} 
import SwiftUI

public struct ChatInput: View {
    @Binding var message: String
    let configuration: ChatConfiguration
    let onSend: () -> Void
    
    public init(message: Binding<String>, configuration: ChatConfiguration, onSend: @escaping () -> Void) {
        self._message = message
        self.configuration = configuration
        self.onSend = onSend
    }
    
    public var body: some View {
        HStack(spacing: 8) {
            TextField("Type a message...", text: $message)
                .textFieldStyle(RoundedBorderTextFieldStyle())
                .padding(.horizontal)
                .background(configuration.inputBackgroundColor)
                .foregroundColor(configuration.inputTextColor)
            
            Button(action: onSend) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 24))
                    .foregroundColor(configuration.sendButtonColor)
            }
            .padding(.trailing)
            .disabled(message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
        .padding(.vertical, 8)
        .background(configuration.inputBackgroundColor)
    }
} 
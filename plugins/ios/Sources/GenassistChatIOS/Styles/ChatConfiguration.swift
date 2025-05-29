import SwiftUI

public struct ChatConfiguration {
    public var backgroundColor: Color
    public var bubbleColor: Color
    public var userBubbleColor: Color
    public var textColor: Color
    public var userTextColor: Color
    public var inputBackgroundColor: Color
    public var inputTextColor: Color
    public var sendButtonColor: Color
    public var cornerRadius: CGFloat
    public var bubblePadding: CGFloat
    public var spacing: CGFloat
    
    public init(
        backgroundColor: Color = .white,
        bubbleColor: Color = Color.gray.opacity(0.1),
        userBubbleColor: Color = .blue,
        textColor: Color = .primary,
        userTextColor: Color = .white,
        inputBackgroundColor: Color = Color.gray.opacity(0.1),
        inputTextColor: Color = .primary,
        sendButtonColor: Color = .blue,
        cornerRadius: CGFloat = 12,
        bubblePadding: CGFloat = 12,
        spacing: CGFloat = 8
    ) {
        self.backgroundColor = backgroundColor
        self.bubbleColor = bubbleColor
        self.userBubbleColor = userBubbleColor
        self.textColor = textColor
        self.userTextColor = userTextColor
        self.inputBackgroundColor = inputBackgroundColor
        self.inputTextColor = inputTextColor
        self.sendButtonColor = sendButtonColor
        self.cornerRadius = cornerRadius
        self.bubblePadding = bubblePadding
        self.spacing = spacing
    }
} 
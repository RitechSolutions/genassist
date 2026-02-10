import SwiftUI
import AVFoundation

// MARK: - Component Configurations

public struct HeaderConfiguration {
    public var backgroundColor: Color
    public var primaryTextColor: Color
    public var titleFont: Font
    public var subtitleFont: Font
    
    public init(
        backgroundColor: Color = Color.white,
        primaryTextColor: Color = .primary,
        titleFont: Font = .headline,
        subtitleFont: Font = .subheadline
    ) {
        self.backgroundColor = backgroundColor
        self.primaryTextColor = primaryTextColor
        self.titleFont = titleFont
        self.subtitleFont = subtitleFont
    }
}

public struct SenderMessageConfiguration {
    public var bubbleColor: Color
    public var textColor: Color
    public var textFont: Font
    public var cornerRadius: CGFloat
    public var padding: CGFloat
    
    public init(
        bubbleColor: Color = Color(red: 228 / 255, green: 228 / 255, blue: 230 / 255),
        textColor: Color = .primary,
        textFont: Font = .body,
        cornerRadius: CGFloat = 12,
        padding: CGFloat = 8
    ) {
        self.bubbleColor = bubbleColor
        self.textColor = textColor
        self.textFont = textFont
        self.cornerRadius = cornerRadius
        self.padding = padding
    }
}

public struct ReceivedMessageConfiguration {
    public var bubbleColor: Color
    public var textColor: Color
    public var textFont: Font
    public var cornerRadius: CGFloat
    public var padding: CGFloat
    
    public init(
        bubbleColor: Color = Color.white,
        textColor: Color = .primary,
        textFont: Font = .body,
        cornerRadius: CGFloat = 12,
        padding: CGFloat = 8
    ) {
        self.bubbleColor = bubbleColor
        self.textColor = textColor
        self.textFont = textFont
        self.cornerRadius = cornerRadius
        self.padding = padding
    }
}

public struct ThinkingPhraseConfiguration {
    public var font: Font
    public var textColor: Color
    public var backgroundColor: Color
    public var cornerRadius: CGFloat
    public var padding: CGFloat
    public var interval: TimeInterval
    
    public init(
        font: Font = .system(size: 14),
        textColor: Color = .secondary,
        backgroundColor: Color = .clear,
        cornerRadius: CGFloat = 0,
        padding: CGFloat = 0,
        interval: TimeInterval = 2.0
    ) {
        self.font = font
        self.textColor = textColor
        self.backgroundColor = backgroundColor
        self.cornerRadius = cornerRadius
        self.padding = padding
        self.interval = interval
    }
}

public struct InputFieldConfiguration {
    public var backgroundColor: Color
    public var textColor: Color
    public var textFont: Font
    public var sendButtonColor: Color
    public var cornerRadius: CGFloat
    public var padding: CGFloat
    public var iconSize: CGFloat

    
    public init(
        backgroundColor: Color = Color(red: 241 / 255, green: 241 / 255, blue: 241 / 255),
        textColor: Color = .primary,
        textFont: Font = .system(size: 14),
        sendButtonColor: Color = Color(red: 187 / 255, green: 39 / 255, blue: 26 / 255),
        cornerRadius: CGFloat = 8,
        padding: CGFloat = 15,
        iconSize: CGFloat = 24
    ) {
        self.backgroundColor = backgroundColor
        self.textColor = textColor
        self.textFont = textFont
        self.sendButtonColor = sendButtonColor
        self.cornerRadius = cornerRadius
        self.padding = padding
        self.iconSize = iconSize
    }
}
//            buttonFont: Font = .body,
//            buttonTextColor: Color = .white,
//            buttonBackgroundColor: Color = Color(red: 187 / 255, green: 39 / 255, blue: 26 / 255),
//            buttonCornerRadius: CGFloat = 12,
//            buttonPadding: CGFloat = 16,
//            buttonSpacing: CGFloat = 12
public enum OptionsOrientation {
    case horizontal
    case vertical
}

public struct OptionsConfiguration {
    public var font: Font
    public var textColor: Color
    public var backgroundColor: Color
    public var cornerRadius: CGFloat
    public var padding: CGFloat
    public var spacing: CGFloat
    public var selectedColor: Color
    public var selectedBackgroundColor: Color
    public var orientation: OptionsOrientation
    public init(font: Font = .body, textColor: Color = .white, backgroundColor: Color = Color(red: 187 / 255, green: 39 / 255, blue: 26 / 255), cornerRadius: CGFloat = 12, padding: CGFloat = 16, spacing: CGFloat = 12, selectedColor: Color = .white, selectedBackgroundColor: Color = Color(red: 187 / 255, green: 39 / 255, blue: 26 / 255), orientation: OptionsOrientation = .horizontal) {
         self.font = font
         self.textColor = textColor
         self.backgroundColor = backgroundColor
         self.cornerRadius = cornerRadius
         self.padding = padding
         self.spacing = spacing
         self.selectedColor = selectedColor
         self.selectedBackgroundColor = selectedBackgroundColor
         self.orientation = orientation
     }
     
}
public struct DynamicItemConfiguration {
    public var titleFont: Font
    public var descriptionFont: Font
    public var titleColor: Color
    public var descriptionColor: Color
    public var backgroundColor: Color
    public var cornerRadius: CGFloat
    public var padding: CGFloat
    public var imageSize: CGFloat
    public var spacing: CGFloat
    
    // Options specific properties (for time slots, events, restaurants, etc.)
    
    public var optionsConfiguration: OptionsConfiguration
    
    // Delete button properties
    public var deleteButtonColor: Color
    public var deleteButtonSize: CGFloat
    public var deleteButtonBackgroundColor: Color
    public var deleteButtonCornerRadius: CGFloat
    
    public init(
        titleFont: Font = .headline,
        descriptionFont: Font = .caption,
        titleColor: Color = .primary,
        descriptionColor: Color = .secondary,
        backgroundColor: Color = Color(red: 0.95, green: 0.95, blue: 0.97),
        cornerRadius: CGFloat = 14,
        padding: CGFloat = 8,
        imageSize: CGFloat = 60,
        spacing: CGFloat = 12,
        optionsConfiguration: OptionsConfiguration = OptionsConfiguration(),
        deleteButtonColor: Color = .red,
        deleteButtonSize: CGFloat = 20,
        deleteButtonBackgroundColor: Color = .white,
        deleteButtonCornerRadius: CGFloat = 10
    ) {
        self.titleFont = titleFont
        self.descriptionFont = descriptionFont
        self.titleColor = titleColor
        self.descriptionColor = descriptionColor
        self.backgroundColor = backgroundColor
        self.cornerRadius = cornerRadius
        self.padding = padding
        self.imageSize = imageSize
        self.spacing = spacing
        self.optionsConfiguration = optionsConfiguration
        self.deleteButtonColor = deleteButtonColor
        self.deleteButtonSize = deleteButtonSize
        self.deleteButtonBackgroundColor = deleteButtonBackgroundColor
        self.deleteButtonCornerRadius = deleteButtonCornerRadius
    }
}

public struct PossibleQueriesConfiguration {
    public var bubbleColor: Color
    public var textColor: Color
    public var textFont: Font
    public var cornerRadius: CGFloat
    public var padding: CGFloat
    public var spacing: CGFloat
    
    public init(
        bubbleColor: Color = Color.red,
        textColor: Color = .primary,
        textFont: Font = .body,
        cornerRadius: CGFloat = 12,
        padding: CGFloat = 8,
        spacing: CGFloat = 8
    ) {
        self.bubbleColor = bubbleColor
        self.textColor = textColor
        self.textFont = textFont
        self.cornerRadius = cornerRadius
        self.padding = padding
        self.spacing = spacing
    }
}

public struct TimestampConfiguration {
    public var timeFont: Font
    public var senderFont: Font
    public var timeColor: Color
    public var senderColor: Color
    public var spacing: CGFloat
    
    public init(
        timeFont: Font = .caption,
        senderFont: Font = .caption.bold(),
        timeColor: Color = .secondary,
        senderColor: Color = .primary,
        spacing: CGFloat = 4
    ) {
        self.timeFont = timeFont
        self.senderFont = senderFont
        self.timeColor = timeColor
        self.senderColor = senderColor
        self.spacing = spacing
    }
}

public struct WelcomeScreenConfiguration {
    public var backgroundColor: Color
    public var cornerRadius: CGFloat
    public var paddingB: CGFloat
    public var paddingT: CGFloat
    public var paddingL: CGFloat
    public var paddingR: CGFloat

    public var spacing: CGFloat
    
    // Avatar/Image properties
    public var avatarSize: CGFloat
    public var avatarCornerRadius: CGFloat
    
    // Title properties
    public var titleFont: Font
    public var titleColor: Color
    
    // Description properties
    public var descriptionFont: Font
    public var descriptionColor: Color
    public var opionsConfiguration: OptionsConfiguration

    public init(
        backgroundColor: Color = .clear,
        cornerRadius: CGFloat = 0,
        paddingT: CGFloat = 0,
        paddingB: CGFloat = 0,
        paddingL: CGFloat = 0,
        paddingR: CGFloat = 0,
        spacing: CGFloat = 16,
        avatarSize: CGFloat = 60,
        avatarCornerRadius: CGFloat = 30,
        titleFont: Font = .title2.bold(),
        titleColor: Color = .primary,
        descriptionFont: Font = .body,
        descriptionColor: Color = .secondary,
        optionsConfiguration: OptionsConfiguration = OptionsConfiguration(),

    ) {

        self.backgroundColor = backgroundColor
        self.cornerRadius = cornerRadius
        self.paddingT = paddingT
        self.paddingB = paddingB
        self.paddingL = paddingL
        self.paddingR = paddingR
        self.spacing = spacing
        self.avatarSize = avatarSize
        self.avatarCornerRadius = avatarCornerRadius
        self.titleFont = titleFont
        self.titleColor = titleColor
        self.descriptionFont = descriptionFont
        self.descriptionColor = descriptionColor
        self.opionsConfiguration = optionsConfiguration
    }

}


// MARK: - Main Chat Configuration

public struct ChatConfiguration {
    public var backgroundColor: Color
    public var spacing: CGFloat
    public var enableTextToSpeech: Bool
    public var speechRate: Float
    public var speechVolume: Float
    public var useVoice: Bool
    
    // Component configurations
    public var header: HeaderConfiguration
    public var senderMessage: SenderMessageConfiguration
    public var receivedMessage: ReceivedMessageConfiguration
    public var thinkingPhrase: ThinkingPhraseConfiguration
    public var inputField: InputFieldConfiguration
    public var dynamicItem: DynamicItemConfiguration
    public var possibleQueries: PossibleQueriesConfiguration
    public var timestamp: TimestampConfiguration
    public var welcomeScreen: WelcomeScreenConfiguration
    public var optionsConfiguration: OptionsConfiguration




    
    public init(
        backgroundColor: Color = Color(red: 244 / 255, green: 244 / 255, blue: 245 / 255),
        spacing: CGFloat = 8,
        enableTextToSpeech: Bool = true,
        speechRate: Float = AVSpeechUtteranceDefaultSpeechRate,
        speechVolume: Float = 0.8,
        useVoice: Bool = true,
        header: HeaderConfiguration = HeaderConfiguration(),
        senderMessage: SenderMessageConfiguration = SenderMessageConfiguration(),
        receivedMessage: ReceivedMessageConfiguration = ReceivedMessageConfiguration(),
        thinkingPhrase: ThinkingPhraseConfiguration = ThinkingPhraseConfiguration(),
        inputField: InputFieldConfiguration = InputFieldConfiguration(),
        dynamicItem: DynamicItemConfiguration = DynamicItemConfiguration(),
        possibleQueries: PossibleQueriesConfiguration = PossibleQueriesConfiguration(),
        timestamp: TimestampConfiguration = TimestampConfiguration(),
        welcomeScreen: WelcomeScreenConfiguration = WelcomeScreenConfiguration(),
        optionsConfiguration: OptionsConfiguration = OptionsConfiguration(),

        ) {
        self.backgroundColor = backgroundColor
        self.spacing = spacing
        self.enableTextToSpeech = enableTextToSpeech
        self.speechRate = speechRate
        self.speechVolume = speechVolume
        self.useVoice = useVoice
        self.header = header
        self.senderMessage = senderMessage
        self.receivedMessage = receivedMessage
        self.thinkingPhrase = thinkingPhrase
        self.inputField = inputField
        self.dynamicItem = dynamicItem
        self.possibleQueries = possibleQueries
        self.timestamp = timestamp
        self.welcomeScreen = welcomeScreen
        self.optionsConfiguration = optionsConfiguration

    }
} 

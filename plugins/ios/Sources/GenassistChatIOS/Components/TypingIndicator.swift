//
//  TypingIndicator.swift
//  GenassistChatIOS
//
//  Created by Krist V on 24.5.25.
//

import SwiftUI

struct EmojiConverter {
    static let shortcodes: [String: String] = [
        ":smile:": "😄",
        ":thumbsup:": "👍",
        ":rocket:": "🚀",
        ":heart:": "❤️",
        ":star:": "⭐️",
        ":speedboat:": "🚤",
        ":thinking_face:": "🤔",
        ":ocean:": "🌊",
        ":knot:": "🪢",
        ":world_map:": "🗺️",
        ":anchor:": "⚓",
        ":tropical_drink:": "🍹",
        ":boat:": "⛵",
        ":wind_blowing_face:": "🌬️",
        ":sunrise:": "🌅"
    ]
}
extension String {
    func withShortcodesConvertedToEmojis() -> String {
        var convertedString = self
        for (shortcode, emoji) in EmojiConverter.shortcodes {
            convertedString = convertedString.replacingOccurrences(of: shortcode, with: emoji)
        }
        return convertedString
    }
}
public struct TypingIndicator: View {
    @State private var animationTrigger = false
    @State private var currentPhrasePart = ""
    @State private var phraseParts: [String] = []
    @State private var currentPartIndex = 0
    @State private var timer: Timer?
    @State private var isTransitioning = false
    let configuration: ChatConfiguration
    let thinkingPhrases: [String]
    
    private let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return formatter
    }()
    
    public init(configuration: ChatConfiguration, thinkingPhrases: [String] = []) {
        self.configuration = configuration
        self.thinkingPhrases = thinkingPhrases
    }
    
    public var body: some View {
        VStack(alignment: .leading, spacing: configuration.timestamp.spacing) {
            // Timestamp and sender label (like user message)
            HStack(spacing: configuration.timestamp.spacing) {

                
                Text("Virtual Angel")
                    .font(configuration.timestamp.senderFont)
                    .foregroundColor(configuration.timestamp.senderColor)
                Text(dateFormatter.string(from: Date()))
                    .font(configuration.timestamp.timeFont)
                    .foregroundColor(configuration.timestamp.timeColor)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            
            // Message bubble (styled like user message)
            HStack {
                
                HStack(spacing: 4) {
                    if !currentPhrasePart.isEmpty {
                        // Show thinking phrase text with smooth transitions
                        Text(currentPhrasePart)
                            .font(configuration.receivedMessage.textFont)
                            .foregroundColor(configuration.receivedMessage.textColor)
                            .multilineTextAlignment(.leading)
                            .opacity(isTransitioning ? 0 : 1)
                            .scaleEffect(isTransitioning ? 0.95 : 1.0)
                            .animation(.easeInOut(duration: 0.3), value: isTransitioning)
                            .animation(.easeInOut(duration: 0.3), value: currentPhrasePart)
                    } else {
                        // Show animated dots
                        ForEach(0..<3) { index in
                            Circle()
                                .fill(configuration.senderMessage.textColor.opacity(0.7))
                                .frame(width: 6, height: 6)
                                .scaleEffect(animationTrigger ? 1.0 : 0.4)
                                .opacity(animationTrigger ? 1.0 : 0.4)
                                .animation(
                                    Animation.easeInOut(duration: 0.6)
                                        .repeatForever()
                                        .delay(0.2 * Double(index)),
                                    value: animationTrigger
                                )
                        }
                    }
                }
                .padding(.horizontal, configuration.receivedMessage.padding)
                .padding(.vertical, configuration.receivedMessage.padding/2)
                .background(configuration.receivedMessage.bubbleColor)
                .cornerRadius(configuration.receivedMessage.cornerRadius)
                Spacer()

            }
        }
        .onAppear {
            setupThinkingPhrases()
            // Start the animation with a small delay to ensure smooth rendering
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                animationTrigger = true
            }
        }
        .onDisappear {
            animationTrigger = false
            timer?.invalidate()
            timer = nil
        }
    }
    
    private func setupThinkingPhrases() {
        // Check if we have more than 1 thinking phrase
        guard thinkingPhrases.count > 1 else {
            currentPhrasePart = ""
            isTransitioning = false
            return
        }
        
        // Randomly select one thinking phrase
        let selectedPhrase = thinkingPhrases.randomElement() ?? ""
        
        // Split by "|" and trim whitespace
        phraseParts = selectedPhrase.components(separatedBy: "|").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        
        // Start with the first part
        currentPartIndex = 0
        currentPhrasePart = phraseParts.first ?? ""
        isTransitioning = false
        
        // Start timer to cycle through parts at configured interval
        startTimer()
    }
    
    private func startTimer() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: configuration.thinkingPhrase.interval, repeats: true) { _ in
            Task { @MainActor in
                // Fade out current phrase
                withAnimation(.easeInOut(duration: 0.3)) {
                    isTransitioning = true
                }
                
                // Wait for fade out to complete, then change text and fade in
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                    currentPartIndex += 1
                    
                    if currentPartIndex < phraseParts.count {
                        currentPhrasePart = phraseParts[currentPartIndex]
                        
                        // Fade in new phrase
                        withAnimation(.easeInOut(duration: 0.3)) {
                            isTransitioning = false
                        }
                    } else {
                        // Reached the end, stop the timer
                        timer?.invalidate()
                        timer = nil
                        isTransitioning = false
                    }
                }
            }
        }
    }
}


#Preview {
    TypingIndicator(configuration: ChatConfiguration())
        .padding()
} 

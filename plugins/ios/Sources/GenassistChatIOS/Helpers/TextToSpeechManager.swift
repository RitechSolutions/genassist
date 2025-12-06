import Foundation
import AVFoundation
import Speech

public class TextToSpeechManager: NSObject, ObservableObject, @unchecked Sendable {
    private let synthesizer = AVSpeechSynthesizer()
    @Published private(set) var isSpeaking: Bool = false
    
    public override init() {
        super.init()
        synthesizer.delegate = self
    }
    
    public func speak(_ text: String, voice: AVSpeechSynthesisVoice? = nil, rate: Float = AVSpeechUtteranceDefaultSpeechRate, volume: Float = 0.8) {
        // Stop any current speech
        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }
        
        let utterance = AVSpeechUtterance(string: text)
        
        // Configure voice settings
        if let voice = voice {
            utterance.voice = voice
        } else {
            // Use system default voice
            utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        }
        
        // Configure speech settings
        utterance.rate = rate
        utterance.pitchMultiplier = 1.0
        utterance.volume = volume
        
        // Start speaking
        synthesizer.speak(utterance)
        DispatchQueue.main.async {
            self.isSpeaking = true
        }
    }
    
    public func stop() {
        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }
        DispatchQueue.main.async {
            self.isSpeaking = false
        }
    }
    
    public func pause() {
        if synthesizer.isSpeaking {
            synthesizer.pauseSpeaking(at: .immediate)
        }
    }
    
    public func continueSpeaking() {
        if synthesizer.isPaused {
            synthesizer.continueSpeaking()
        }
    }
    
    public func getAvailableVoices() -> [AVSpeechSynthesisVoice] {
        return AVSpeechSynthesisVoice.speechVoices()
    }
    
    public func getVoice(for language: String) -> AVSpeechSynthesisVoice? {
        return AVSpeechSynthesisVoice(language: language)
    }
}

// MARK: - AVSpeechSynthesizerDelegate
extension TextToSpeechManager: AVSpeechSynthesizerDelegate {
    public func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didStart utterance: AVSpeechUtterance) {
        DispatchQueue.main.async {
            self.isSpeaking = true
        }
    }
    
    public func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        DispatchQueue.main.async {
            self.isSpeaking = false
        }
    }
    
    public func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        DispatchQueue.main.async {
            self.isSpeaking = false
        }
    }
    
    public func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didPause utterance: AVSpeechUtterance) {
        // Handle pause if needed
    }
    
    public func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didContinue utterance: AVSpeechUtterance) {
        // Handle continue if needed
    }
} 
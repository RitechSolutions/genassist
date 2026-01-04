import Foundation
import AVFoundation

public class SoundManager {
    private var startRecordingPlayer: AVAudioPlayer?
    private var stopRecordingPlayer: AVAudioPlayer?
    
    public init() {
        setupAudioPlayers()
    }
    
    private func setupAudioPlayers() {
        // Create system sound IDs for recording feedback
        // These will use the system's built-in sounds for better user experience
        setupSystemSounds()
    }
    
    private func setupSystemSounds() {
        // For iOS, we'll use system sounds that are commonly used for recording feedback
        // These are built into the system and don't require additional audio files
    }
    
    public func playRecordingStartSound() {
        // Play a short beep sound to indicate recording has started
        AudioServicesPlaySystemSound(1103) // System sound for recording start
    }
    
    public func playRecordingStopSound() {
        // Play a different sound to indicate recording has stopped
        AudioServicesPlaySystemSound(1104) // System sound for recording stop
    }
    
    // Alternative method using custom audio files if needed
    public func playCustomSound(named soundName: String) {
        guard let url = Bundle.main.url(forResource: soundName, withExtension: "wav") else {
            print("Sound file not found: \(soundName)")
            return
        }
        
        do {
            let player = try AVAudioPlayer(contentsOf: url)
            player.prepareToPlay()
            player.play()
        } catch {
            print("Error playing sound: \(error)")
        }
    }
} 
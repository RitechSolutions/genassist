import Foundation
import AVFoundation

public class SoundManager {
    private var startRecordingPlayer: AVAudioPlayer?
    private var stopRecordingPlayer: AVAudioPlayer?
    
    public init() {
        setupAudioPlayers()
    }
    
    private func setupAudioPlayers() {
        setupSystemSounds()
    }
    
    private func setupSystemSounds() {
        // Uses built-in system sounds, so there is nothing to preload.
    }
    
    public func playRecordingStartSound() {
        AudioServicesPlaySystemSound(1103) // System sound for recording start
    }
    
    public func playRecordingStopSound() {
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
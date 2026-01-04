import Foundation
import AVFoundation
import Speech
import Observation
import SwiftUI
import Combine

/// A helper for transcribing speech to text using SFSpeechRecognizer and AVAudioEngine.
public actor SpeechRecognizer: Observable {
    public enum RecognizerError: Error {
        case nilRecognizer
        case notAuthorizedToRecognize
        case notPermittedToRecord
        case recognizerIsUnavailable
        
        public var message: String {
            switch self {
            case .nilRecognizer: return "Can't initialize speech recognizer"
            case .notAuthorizedToRecognize: return "Not authorized to recognize speech"
            case .notPermittedToRecord: return "Not permitted to record audio"
            case .recognizerIsUnavailable: return "Recognizer is unavailable"
            }
        }
    }
    
    @MainActor public var transcript: String = ""
    
    private var audioEngine: AVAudioEngine?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private let recognizer: SFSpeechRecognizer?
    
    /**
     Initializes a new speech recognizer without requesting permissions.
     Permissions will be requested when startTranscribing() is called.
     */
    public init() {
        recognizer = SFSpeechRecognizer()
    }
    
    @MainActor public func startTranscribing() {
        Task {
            // Check permissions before starting transcription
            do {
//                guard let recognizer = recognizer, recognizer.isAvailable else {
//                    throw RecognizerError.recognizerIsUnavailable
//                }
                guard await SFSpeechRecognizer.hasAuthorizationToRecognize() else {
                    throw RecognizerError.notAuthorizedToRecognize
                }
                guard await AVAudioSession.sharedInstance().hasPermissionToRecord() else {
                    throw RecognizerError.notPermittedToRecord
                }
                
                // If we get here, permissions are granted, so start transcribing
                await transcribe()
            } catch {
                transcribe(error)
            }
        }
    }
    
    @MainActor public func resetTranscript() {
        Task {
            await reset()
        }
    }
    
    @MainActor public func stopTranscribing() {
        Task {
            await reset()
        }
    }
    
    /**
     Begin transcribing audio.
     
     Creates a `SFSpeechRecognitionTask` that transcribes speech to text until you call `stopTranscribing()`.
     The resulting transcription is continuously written to the published `transcript` property.
     Note: Permissions are checked in startTranscribing() before this method is called.
     */
    private func transcribe() {
        do {
            let (audioEngine, request) = try Self.prepareEngine()
            self.audioEngine = audioEngine
            self.request = request
            self.task = recognizer?.recognitionTask(with: request, resultHandler: { [weak self] result, error in
                self?.recognitionHandler(audioEngine: audioEngine, result: result, error: error)
            })
        } catch {
            self.reset()
            self.transcribe(error)
        }
    }
    
    /// Reset the speech recognizer.
    private func reset() {
        task?.cancel()
        audioEngine?.stop()
        audioEngine = nil
        request = nil
        task = nil
    }
    
    private static func prepareEngine() throws -> (AVAudioEngine, SFSpeechAudioBufferRecognitionRequest) {
        let audioEngine = AVAudioEngine()
        
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        
        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(.playAndRecord, mode: .measurement, options: .duckOthers)
        try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
        let inputNode = audioEngine.inputNode
        
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { (buffer: AVAudioPCMBuffer, when: AVAudioTime) in
            request.append(buffer)
        }
        audioEngine.prepare()
        try audioEngine.start()
        
        return (audioEngine, request)
    }
    
    nonisolated private func recognitionHandler(audioEngine: AVAudioEngine, result: SFSpeechRecognitionResult?, error: Error?) {
        let receivedFinalResult = result?.isFinal ?? false
        let receivedError = error != nil
        
        if receivedFinalResult || receivedError {
            audioEngine.stop()
            audioEngine.inputNode.removeTap(onBus: 0)
        }
        
        if let result {
            transcribe(result.bestTranscription.formattedString)
        }
    }
    
    
    nonisolated private func transcribe(_ message: String) {
        Task { @MainActor in
            transcript = message
        }
    }
    nonisolated private func transcribe(_ error: Error) {
        var errorMessage = ""
        if let error = error as? RecognizerError {
            errorMessage += error.message
        } else {
            errorMessage += error.localizedDescription
        }
        Task { @MainActor [errorMessage] in
            transcript = "<< \(errorMessage) >>"
        }
    }
}


extension SFSpeechRecognizer {
    static func hasAuthorizationToRecognize() async -> Bool {
        await withCheckedContinuation { continuation in
            requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }
    }
}


extension AVAudioSession {
    func hasPermissionToRecord() async -> Bool {
        await withCheckedContinuation { continuation in
            if #available(iOS 17.0, *) {
                AVAudioApplication.requestRecordPermission { authorized in
                    continuation.resume(returning: authorized)
                }
            } else {
                // Fallback on earlier versions
            }
        }
    }
}


@MainActor
class SpeechRecognizerViewModel: ObservableObject {
    @Published var transcript: String = ""
    @Published var hasPermissions: Bool = false
    @Published var permissionError: String? = nil
    
    private let recognizer = SpeechRecognizer()

    init() {
        // No automatic permission requests on init
    }
    
    /// Check if permissions are available without requesting them
    func checkPermissions() async {
        let speechAuth = await SFSpeechRecognizer.hasAuthorizationToRecognize()
        let audioAuth = await AVAudioSession.sharedInstance().hasPermissionToRecord()
        hasPermissions = speechAuth && audioAuth
    }

    func start() async {
        // Clear any previous errors
        permissionError = nil
        
        recognizer.startTranscribing()
        monitorTranscript()
    }

    func stop() {
        recognizer.stopTranscribing()
    }

    private func monitorTranscript() {
        // Continuously poll the actor's transcript
        Task {
            while true {
                try? await Task.sleep(nanoseconds: 300_000_000) // 0.3s
                let currentTranscript = await recognizer.transcript
                
                // Check if there's an error message in the transcript
                if currentTranscript.hasPrefix("<<") && currentTranscript.hasSuffix(">>") {
                    let errorMessage = String(currentTranscript.dropFirst(3).dropLast(3))
                    permissionError = errorMessage
                    hasPermissions = false
                    break // Stop monitoring on error
                } else {
                    self.transcript = currentTranscript
                }
            }
        }
    }

    func reset() {
        recognizer.resetTranscript()
        permissionError = nil
    }
}

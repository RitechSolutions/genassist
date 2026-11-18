// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "GenassistChatIOS",
    platforms: [
        SupportedPlatform
            .iOS(.v15),
        SupportedPlatform
            .macOS(.v12)
        
    ],
    products: [
        .library(
            name: "GenassistChatIOS",
            targets: ["GenassistChatIOS"]),
    ],
    targets: [
        .target(
            name: "GenassistChatIOS"),
        .testTarget(
            name: "GenassistChatIOSTests",
            dependencies: ["GenassistChatIOS"]
        ),
    ]
)

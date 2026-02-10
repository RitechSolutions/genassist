import SwiftUI

public struct WelcomeScreenView: View {
    let welcomeScreenData: WelcomeScreenData
    let configuration: ChatConfiguration
    let onQueryTap: ((String) -> Void)?
    
    public init(welcomeScreenData: WelcomeScreenData, configuration: ChatConfiguration, onQueryTap: ((String) -> Void)? = nil) {
        self.welcomeScreenData = welcomeScreenData
        self.configuration = configuration
        self.onQueryTap = onQueryTap
    }
    
    public var body: some View {
        VStack(alignment: .leading, spacing: configuration.welcomeScreen.spacing) {
            // Image on top
            if let imageURL = welcomeScreenData.imageURL, !imageURL.isEmpty {
                AsyncImage(url: URL(string: imageURL)) { image in
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                } placeholder: {
                    // Default avatar placeholder
                    Circle()
                        .fill(Color.red)
                        .overlay(
                            Image(systemName: "person.fill")
                                .foregroundColor(.white)
                                .font(.title2)
                        )
                }
                .frame(width: configuration.welcomeScreen.avatarSize, height: configuration.welcomeScreen.avatarSize)
                .clipShape(Circle())
            }
            
            // Title with anchor emoji
            HStack(spacing: 4) {
                Text(welcomeScreenData.title)
                    .font(configuration.welcomeScreen.titleFont)
                    .foregroundColor(configuration.welcomeScreen.titleColor)
            }
            
            // Description
            Text(welcomeScreenData.description)
                .font(configuration.welcomeScreen.descriptionFont)
                .foregroundColor(configuration.welcomeScreen.descriptionColor)
                .multilineTextAlignment(.leading)
            
            // Possible Queries Buttons
            if !welcomeScreenData.possibleQueries.isEmpty {
                if configuration.welcomeScreen.opionsConfiguration.orientation == .vertical {
                    VStack(alignment: .leading, spacing: configuration.welcomeScreen.opionsConfiguration.spacing) {
                        ForEach(welcomeScreenData.possibleQueries, id: \.self) { query in
                            Button(action: {
                                onQueryTap?(query)
                            }) {
                                HStack(spacing: 8) {
                                    Text(query)
                                        .font(configuration.welcomeScreen.opionsConfiguration.font)
                                        .foregroundColor(configuration.welcomeScreen.opionsConfiguration.textColor)
                                }
                                .padding(.horizontal, configuration.welcomeScreen.opionsConfiguration.padding)
                                .padding(.vertical, configuration.welcomeScreen.opionsConfiguration.padding / 2)
                                .background(configuration.welcomeScreen.opionsConfiguration.backgroundColor)
                                .cornerRadius(configuration.welcomeScreen.opionsConfiguration.cornerRadius)
                            }
                            .buttonStyle(PlainButtonStyle())
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                } else {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: configuration.welcomeScreen.opionsConfiguration.spacing) {
                            ForEach(welcomeScreenData.possibleQueries, id: \.self) { query in
                                Button(action: {
                                    onQueryTap?(query)
                                }) {
                                    HStack(spacing: 8) {
                                        Text(query)
                                            .font(configuration.welcomeScreen.opionsConfiguration.font)
                                            .foregroundColor(configuration.welcomeScreen.opionsConfiguration.textColor)
                                    }
                                    .padding(.horizontal, configuration.welcomeScreen.opionsConfiguration.padding)
                                    .padding(.vertical, configuration.welcomeScreen.opionsConfiguration.padding / 2)
                                    .background(configuration.welcomeScreen.opionsConfiguration.backgroundColor)
                                    .cornerRadius(configuration.welcomeScreen.opionsConfiguration.cornerRadius)
                                }
                                .buttonStyle(PlainButtonStyle())
                            }
                        }
                        .padding(.horizontal, 4)
                    }
                }
            }
        }
        .padding(.top,configuration.welcomeScreen.paddingT)
        .padding(.bottom,configuration.welcomeScreen.paddingB)
        .padding(.leading,configuration.welcomeScreen.paddingL)
        .padding(.trailing,configuration.welcomeScreen.paddingR)

        .background(configuration.welcomeScreen.backgroundColor)
        .cornerRadius(configuration.welcomeScreen.cornerRadius)
    }
    

}

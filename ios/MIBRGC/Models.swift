import Foundation
import SwiftUI

struct TeamBrief: Decodable, Identifiable {
    let id: String
    let label: String
    let scopes: [PlayScope]
}

struct Brief: Decodable {
    let year: Int
    let teams: [TeamBrief]

    static func load() -> Brief? {
        guard let url = Bundle.main.url(forResource: "brief", withExtension: "json"),
              let data = try? Data(contentsOf: url) else {
            return nil
        }
        return try? JSONDecoder().decode(Brief.self, from: data)
    }
}

struct PlayScope: Decodable, Identifiable {
    let id: String
    let name: [String: String]
    let note: [String: String]
    let headline: Headline
    let maps: [MapBar]
    let economy: [EconomyBar]
    let liquid: Liquid
    let copy: [String: Copy]
}

struct Headline: Decodable {
    let series: String
    let maps: String
    let roundDiff: Int
    let attack: Double?
    let defense: Double?
}

struct EconomyPlan: Decodable, Identifiable {
    let key: String
    let won: Int
    let played: Int
    let rate: Double
    let title: String
    let line: String
    let why: String
    var id: String { key }
    var lost: Int { played - won }
}

struct EconomyBar: Decodable, Identifiable {
    let key: String
    let won: Int
    let played: Int
    let rate: Double
    var id: String { key }
}

struct MapBar: Decodable, Identifiable {
    let map: String
    let wins: Int
    let losses: Int
    let attack: Double?
    let defense: Double?
    let decision: String
    var id: String { map }
    var record: String { "\(wins)-\(losses)" }
}

struct Liquid: Decodable {
    let seriesRecord: String
    let mapRecord: String
    let roundDiff: Int
    let attack: Double?
    let defense: Double?
    let series: [SeriesRow]
    let maps: [LiquidMap]
    let players: [PlayerBar]
}

struct SeriesRow: Decodable, Identifiable {
    let date: String
    let event: String
    let stage: String
    let score: String
    let result: String
    let url: String
    var id: String { url }
}

struct LiquidMap: Decodable, Identifiable {
    let map: String
    let wins: Int
    let losses: Int
    let attack: Double?
    let defense: Double?
    let roundDiff: Int
    var id: String { map }
    var record: String { "\(wins)-\(losses)" }
}

struct PlayerBar: Decodable, Identifiable {
    let player: String
    let rating: Double?
    let acs: Double?
    let kast: Double?
    let fk: Int
    var id: String { player }
}

struct Copy: Decodable {
    let title: String
    let caption: String
    let report: String
    let liquid: String
    let veto: String
    let cues: String
    let series: String
    let maps: String
    let roundDiff: String
    let attack: String
    let defense: String
    let call: String
    let contactLabel: String
    let say: String
    let roster: String
    let opponent: String
    let seriesHeading: String
    let mapsHeading: String
    let rosterHeading: String
    let vetoHeading: String
    let vetoCaption: String
    let cuesHeading: String
    let cuesCaption: String
    let win: String
    let loss: String
    let rating: String
    let economy: String
    let economyNote: String
    let economyLabels: [String: String]
    let economyPlans: [EconomyPlan]
    let contact: String
    let liquidRead: String
    let steps: [Step]
    let cueCards: [Cue]
    let rosterCards: [RosterCard]
}

struct Step: Decodable, Identifiable {
    let key: String
    let title: String
    let detail: String
    var id: String { title + detail }
}

struct Cue: Decodable, Identifiable {
    let title: String
    let line: String
    let why: String
    var id: String { title }
}

struct RosterCard: Decodable, Identifiable {
    let player: String
    let role: String
    let detail: String
    var id: String { player }
}

final class BriefModel: ObservableObject {
    @Published var language: String
    @Published var scopeId: String
    @Published var teamId: String?
    let brief: Brief?

    init() {
        var storedLanguage = UserDefaults.standard.string(forKey: "language") ?? "en"
        var storedScope = UserDefaults.standard.string(forKey: "scope") ?? "brazil"
        var storedTeam: String? = nil
        let args = ProcessInfo.processInfo.arguments
        if let index = args.firstIndex(of: "-lang"), index + 1 < args.count {
            storedLanguage = args[index + 1]
        }
        if let index = args.firstIndex(of: "-scope"), index + 1 < args.count {
            storedScope = args[index + 1]
        }
        if let index = args.firstIndex(of: "-team"), index + 1 < args.count {
            storedTeam = args[index + 1]
        }
        language = storedLanguage
        scopeId = storedScope
        teamId = storedTeam
        brief = Brief.load()
    }

    var team: TeamBrief? {
        guard let teams = brief?.teams else { return nil }
        return teams.first { $0.id == teamId }
    }

    var sheet: PlayScope? {
        guard let scopes = team?.scopes, !scopes.isEmpty else { return nil }
        return scopes.first { $0.id == scopeId } ?? scopes[0]
    }

    var text: Copy? {
        guard let sheet = sheet else { return nil }
        return sheet.copy[language] ?? sheet.copy["en"]
    }

    func select(_ language: String) {
        self.language = language
        UserDefaults.standard.set(language, forKey: "language")
    }

    func selectScope(_ scopeId: String) {
        self.scopeId = scopeId
        UserDefaults.standard.set(scopeId, forKey: "scope")
    }

    func selectTeam(_ teamId: String) {
        self.teamId = teamId
        self.scopeId = "brazil"
    }

    func showTeams() {
        teamId = nil
    }
}

enum Theme {
    static let background = Color(red: 0.06, green: 0.07, blue: 0.09)
    static let card = Color(red: 0.12, green: 0.14, blue: 0.17)
    static let muted = Color(red: 0.62, green: 0.66, blue: 0.72)
    static let win = Color(red: 0.30, green: 0.82, blue: 0.55)
    static let loss = Color(red: 0.91, green: 0.39, blue: 0.34)
    static let attack = Color(red: 0.95, green: 0.70, blue: 0.27)
    static let defense = Color(red: 0.42, green: 0.64, blue: 0.96)

    static func decision(_ name: String) -> Color {
        switch name {
        case "Ban":
            return loss
        case "Attack side":
            return attack
        case "Defense side":
            return defense
        case "Keep":
            return win
        default:
            return muted
        }
    }
}

func percent(_ value: Double?) -> String {
    guard let value = value else { return "—" }
    return "\(Int((value * 100).rounded()))%"
}

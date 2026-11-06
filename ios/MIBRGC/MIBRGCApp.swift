import SwiftUI

@main
struct MIBRGCApp: App {
    @StateObject private var model = BriefModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(model)
        }
    }
}

struct TeamPicker: View {
    @EnvironmentObject var model: BriefModel

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Game Changers \(model.brief?.year ?? 2026)")
                .font(.caption)
                .foregroundColor(Theme.muted)
            Text(model.language == "pt" ? "Escolha o elenco" : "Choose a roster")
                .font(.title2)
                .foregroundColor(.white)
            ForEach(model.brief?.teams ?? []) { team in
                Button(action: { model.selectTeam(team.id) }) {
                    HStack {
                        Text(team.label)
                            .font(.title3)
                            .foregroundColor(.white)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .foregroundColor(Theme.muted)
                    }
                    .padding(20)
                    .background(Theme.card)
                    .cornerRadius(16)
                }
            }
            Spacer()
            Picker("Language", selection: Binding(
                get: { model.language },
                set: { model.select($0) }
            )) {
                Text("EN").tag("en")
                Text("PT").tag("pt")
            }
            .pickerStyle(SegmentedPickerStyle())
            .frame(width: 140)
        }
        .padding(20)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Theme.background.ignoresSafeArea())
    }
}

struct RootView: View {
    @EnvironmentObject var model: BriefModel
    @State private var tab = "report"

    var body: some View {
        Group {
            if model.team == nil {
                TeamPicker()
            } else if let sheet = model.sheet, let text = model.text {
                VStack(spacing: 0) {
                    header(sheet, text)
                    TabView(selection: $tab) {
                        ReportView(sheet: sheet, text: text)
                            .tabItem {
                                Image(systemName: "chart.bar.fill")
                                Text(text.report)
                            }
                            .tag("report")
                        LiquidView(sheet: sheet, text: text)
                            .tabItem {
                                Image(systemName: "flag.fill")
                                Text(text.liquid)
                            }
                            .tag("liquid")
                        VetoView(text: text)
                            .tabItem {
                                Image(systemName: "map.fill")
                                Text(text.veto)
                            }
                            .tag("veto")
                        CuesView(text: text)
                            .tabItem {
                                Image(systemName: "text.bubble.fill")
                                Text(text.cues)
                            }
                            .tag("cues")
                    }
                    .accentColor(Theme.win)
                }
            } else {
                Text("Missing brief.json. Run python -m matchday.export_ios.")
                    .foregroundColor(.white)
                    .padding()
            }
        }
        .background(Theme.background.ignoresSafeArea())
        .preferredColorScheme(.dark)
    }

    private func header(_ sheet: PlayScope, _ text: Copy) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Button(action: { model.showTeams() }) {
                    Image(systemName: "chevron.left")
                        .foregroundColor(.white)
                }
                Text(text.title)
                    .font(.headline)
                    .foregroundColor(.white)
                    .lineLimit(1)
                Spacer()
                Picker("Language", selection: Binding(
                    get: { model.language },
                    set: { model.select($0) }
                )) {
                    Text("EN").tag("en")
                    Text("PT").tag("pt")
                }
                .pickerStyle(SegmentedPickerStyle())
                .frame(width: 110)
            }
            if let scopes = model.team?.scopes {
                Picker("Circuit", selection: Binding(
                    get: { model.scopeId },
                    set: { model.selectScope($0) }
                )) {
                    ForEach(scopes) { scope in
                        Text(scope.name[model.language] ?? scope.id).tag(scope.id)
                    }
                }
                .pickerStyle(SegmentedPickerStyle())
            }
            Text(text.caption)
                .font(.caption)
                .foregroundColor(Theme.muted)
            Text(sheet.note[model.language] ?? "")
                .font(.caption)
                .foregroundColor(Theme.muted)
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, 10)
        .background(Theme.background)
    }
}

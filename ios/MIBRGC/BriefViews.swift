import SwiftUI

struct ReportView: View {
    let sheet: PlayScope
    let text: Copy

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                metricGrid
                sideCompare
                economyPlans
                mapChart
                callout(text.call, steps: text.steps.filter { ["ban", "first", "attack", "defense"].contains($0.key) })
                if !text.contact.isEmpty {
                    noteCard(title: text.contactLabel, body: text.contact)
                }
                VStack(alignment: .leading, spacing: 8) {
                    sectionTitle(text.say)
                    ForEach(text.cueCards) { cue in
                        noteCard(title: cue.title, body: cue.line)
                    }
                }
                roster
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)
            .padding(.bottom, 88)
        }
    }

    private var metricGrid: some View {
        VStack(spacing: 8) {
            HStack(spacing: 8) {
                MetricTile(title: text.series, value: sheet.headline.series)
                MetricTile(title: text.maps, value: sheet.headline.maps)
            }
            HStack(spacing: 8) {
                MetricTile(title: text.roundDiff, value: signed(sheet.headline.roundDiff))
                MetricTile(title: text.attack, value: percent(sheet.headline.attack))
                MetricTile(title: text.defense, value: percent(sheet.headline.defense))
            }
        }
    }

    private var sideCompare: some View {
        VStack(alignment: .leading, spacing: 8) {
            RateRow(label: text.attack, rate: sheet.headline.attack, color: Theme.attack)
            RateRow(label: text.defense, rate: sheet.headline.defense, color: Theme.defense)
        }
        .padding(14)
        .background(Theme.card)
        .cornerRadius(16)
    }

    private var economyPlans: some View {
        VStack(alignment: .leading, spacing: 10) {
            sectionTitle(text.economy)
            ForEach(text.economyPlans) { plan in
                VStack(alignment: .leading, spacing: 8) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(plan.title)
                            .font(.subheadline)
                            .foregroundColor(.white)
                        Spacer()
                        Text(lossLabel(plan))
                            .font(.system(size: 16, weight: .semibold, design: .rounded))
                            .foregroundColor(Theme.loss)
                    }
                    SplitBar(wins: plan.won, losses: plan.lost)
                    Text(plan.line)
                        .font(.subheadline)
                        .foregroundColor(.white)
                    Text(plan.why)
                        .font(.caption)
                        .foregroundColor(Theme.muted)
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Theme.card)
                .cornerRadius(14)
            }
        }
    }

    private func lossLabel(_ plan: EconomyPlan) -> String {
        let share = plan.played == 0 ? 0 : Int((Double(plan.lost) / Double(plan.played) * 100).rounded())
        return "\(share)%"
    }

    private var mapChart: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle(text.maps)
            ForEach(sheet.maps) { map in
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Circle().fill(Theme.decision(map.decision)).frame(width: 8, height: 8)
                        Text(map.map).foregroundColor(.white).font(.subheadline)
                        Spacer()
                        Text(map.record)
                            .font(.system(size: 13, weight: .semibold, design: .rounded))
                            .foregroundColor(.white)
                    }
                    SplitBar(wins: map.wins, losses: map.losses)
                    HStack(spacing: 12) {
                        Text("\(text.attack) \(percent(map.attack))")
                        Text("\(text.defense) \(percent(map.defense))")
                    }
                    .font(.caption)
                    .foregroundColor(Theme.muted)
                }
            }
        }
        .padding(14)
        .background(Theme.card)
        .cornerRadius(16)
    }

    private var roster: some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionTitle(text.roster)
            ForEach(text.rosterCards) { card in
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(card.player) · \(card.role)")
                        .font(.subheadline)
                        .foregroundColor(.white)
                    Text(card.detail)
                        .font(.caption)
                        .foregroundColor(Theme.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(12)
                .background(Theme.card)
                .cornerRadius(14)
            }
        }
    }

    private func callout(_ title: String, steps: [Step]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionTitle(title)
            ForEach(steps) { step in
                HStack(alignment: .top, spacing: 10) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Theme.decision(step.key == "ban" ? "Ban" : step.key == "attack" ? "Attack side" : step.key == "defense" ? "Defense side" : "Keep"))
                        .frame(width: 4)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(step.title).font(.subheadline).foregroundColor(.white)
                        Text(step.detail).font(.caption).foregroundColor(Theme.muted)
                    }
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Theme.card)
                .cornerRadius(14)
            }
        }
    }
}

struct LiquidView: View {
    let sheet: PlayScope
    let text: Copy

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(text.opponent)
                    .font(.title3)
                    .foregroundColor(.white)
                Text(text.liquidRead)
                    .font(.subheadline)
                    .foregroundColor(Theme.muted)
                HStack(spacing: 8) {
                    MetricTile(title: text.series, value: sheet.liquid.seriesRecord)
                    MetricTile(title: text.maps, value: sheet.liquid.mapRecord)
                    MetricTile(title: text.roundDiff, value: signed(sheet.liquid.roundDiff))
                }
                sectionTitle(text.seriesHeading)
                ForEach(sheet.liquid.series) { row in
                    SeriesCard(row: row, win: text.win, loss: text.loss)
                }
                VStack(alignment: .leading, spacing: 12) {
                    sectionTitle(text.mapsHeading)
                    ForEach(sheet.liquid.maps) { map in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(map.map).foregroundColor(.white)
                                Spacer()
                                Text(map.record).foregroundColor(.white).font(.system(size: 13, weight: .semibold, design: .rounded))
                                Text(signed(map.roundDiff)).foregroundColor(Theme.muted).font(.caption)
                            }
                            SplitBar(wins: map.wins, losses: map.losses)
                        }
                    }
                }
                .padding(14)
                .background(Theme.card)
                .cornerRadius(16)
                sectionTitle(text.rosterHeading)
                ForEach(sheet.liquid.players) { player in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(player.player).foregroundColor(.white)
                            Spacer()
                            Text(String(format: "%.2f", player.rating ?? 0))
                                .font(.system(size: 16, weight: .semibold, design: .rounded))
                                .foregroundColor(.white)
                        }
                        RateRow(label: text.rating, rate: min((player.rating ?? 0) / 1.4, 1), color: Theme.win)
                        Text("ACS \(Int((player.acs ?? 0).rounded())) · KAST \(percent(player.kast)) · FK \(player.fk)")
                            .font(.caption)
                            .foregroundColor(Theme.muted)
                    }
                    .padding(12)
                    .background(Theme.card)
                    .cornerRadius(14)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)
            .padding(.bottom, 88)
        }
    }
}

struct VetoView: View {
    let text: Copy

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text(text.vetoHeading).font(.title3).foregroundColor(.white)
                Text(text.vetoCaption).font(.caption).foregroundColor(Theme.muted)
                ForEach(Array(text.steps.enumerated()), id: \.element.id) { index, step in
                    HStack(alignment: .top, spacing: 12) {
                        Text("\(index + 1)")
                            .font(.system(size: 16, weight: .bold, design: .rounded))
                            .foregroundColor(.black)
                            .frame(width: 28, height: 28)
                            .background(stripe(step.key))
                            .cornerRadius(8)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(step.title).font(.subheadline).foregroundColor(.white)
                            Text(step.detail).font(.caption).foregroundColor(Theme.muted)
                        }
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.card)
                    .cornerRadius(14)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)
            .padding(.bottom, 88)
        }
    }

    private func stripe(_ key: String) -> Color {
        switch key {
        case "ban": return Theme.loss
        case "attack": return Theme.attack
        case "defense": return Theme.defense
        case "available": return Theme.muted
        default: return Theme.win
        }
    }
}

struct CuesView: View {
    let text: Copy

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text(text.cuesHeading).font(.title3).foregroundColor(.white)
                Text(text.cuesCaption).font(.caption).foregroundColor(Theme.muted)
                ForEach(Array(text.cueCards.enumerated()), id: \.element.id) { index, cue in
                    VStack(alignment: .leading, spacing: 8) {
                        Text(String(format: "%02d", index + 1))
                            .font(.system(size: 28, weight: .bold, design: .rounded))
                            .foregroundColor(Theme.win)
                        Text(cue.title).font(.headline).foregroundColor(.white)
                        Text(cue.line).font(.body).foregroundColor(.white)
                        Text(cue.why).font(.caption).foregroundColor(Theme.muted)
                    }
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.card)
                    .cornerRadius(18)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)
            .padding(.bottom, 88)
        }
    }
}

struct MetricTile: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.caption).foregroundColor(Theme.muted)
            Text(value)
                .font(.system(size: 20, weight: .semibold, design: .rounded))
                .foregroundColor(.white)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Theme.card)
        .cornerRadius(14)
    }
}

struct SplitBar: View {
    let wins: Int
    let losses: Int

    var body: some View {
        GeometryReader { geo in
            let total = CGFloat(max(wins + losses, 1))
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.loss.opacity(0.85))
                Capsule()
                    .fill(Theme.win)
                    .frame(width: geo.size.width * CGFloat(wins) / total)
            }
        }
        .frame(height: 10)
    }
}

struct RateRow: View {
    let label: String
    let rate: Double?
    let color: Color

    var body: some View {
        HStack(spacing: 8) {
            Text(label).font(.caption).foregroundColor(Theme.muted).frame(width: 72, alignment: .leading)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(color.opacity(0.2))
                    Capsule().fill(color).frame(width: geo.size.width * CGFloat(min(max(rate ?? 0, 0), 1)))
                }
            }
            .frame(height: 8)
            Text(percent(rate)).font(.caption).foregroundColor(.white).frame(width: 40, alignment: .trailing)
        }
    }
}

struct SeriesCard: View {
    let row: SeriesRow
    let win: String
    let loss: String

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(row.date).font(.caption).foregroundColor(Theme.muted)
                Text(row.event).font(.subheadline).foregroundColor(.white).lineLimit(2)
                Text(row.stage).font(.caption).foregroundColor(Theme.muted).lineLimit(1)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                Text(row.score)
                    .font(.system(size: 18, weight: .bold, design: .rounded))
                    .foregroundColor(.white)
                Text(row.result == "win" ? win : loss)
                    .font(.caption)
                    .foregroundColor(row.result == "win" ? Theme.win : Theme.loss)
            }
        }
        .padding(12)
        .background(Theme.card)
        .cornerRadius(14)
    }
}

private func sectionTitle(_ title: String) -> some View {
    Text(title).font(.headline).foregroundColor(.white)
}

private func noteCard(title: String, body: String) -> some View {
    VStack(alignment: .leading, spacing: 4) {
        Text(title).font(.subheadline).foregroundColor(.white)
        Text(body).font(.caption).foregroundColor(Theme.muted)
    }
    .frame(maxWidth: .infinity, alignment: .leading)
    .padding(12)
    .background(Theme.card)
    .cornerRadius(14)
}

private func signed(_ value: Int) -> String {
    value > 0 ? "+\(value)" : "\(value)"
}

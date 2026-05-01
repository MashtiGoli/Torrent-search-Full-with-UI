import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls.Material 2.15

ApplicationWindow {
    id: root
    visible: true
    width: 1280
    height: 800
    minimumWidth: 900
    minimumHeight: 600
    title: "TorrentSearch — Multi-Engine Aggregator"

    Material.theme: Material.Dark
    Material.accent: "#4ecdc4"

    // ── Theme colours ──────────────────────────────────────────────
    readonly property color bg0:      "#080c14"
    readonly property color bg1:      "#0f1520"
    readonly property color bg2:      "#131d2e"
    readonly property color bg3:      "#1a2640"
    readonly property color accent:   "#4ecdc4"
    readonly property color accentD:  "#2e9e96"
    readonly property color gold:     "#f0b429"
    readonly property color pink:     "#ff79c6"
    readonly property color muted:    "#445566"
    readonly property color text:     "#dde3ea"
    readonly property color textDim:  "#778ca3"

    // ── Background ─────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.bg0 }
            GradientStop { position: 1.0; color: root.bg1 }
        }
    }

    // ── Data model ─────────────────────────────────────────────────
    ListModel { id: resultsModel }

    property int  sortColumn: 0   // 0=date 1=seeds 2=name 3=size
    property bool sortAsc:   false
    property var  allResults: []  // raw JS array for sorting

    // ── Engine enable flags (parallel arrays for QML compatibility) ─
    property var engineNames:   ["LimeTorrents","PirateBay","EZTV","TorLock","SolidTorrents","TorrentsCSV"]
    property var engineStates:  [true, true, true, true, true, true]

    function isEngineEnabled(name) {
        var idx = engineNames.indexOf(name)
        return idx >= 0 ? engineStates[idx] : true
    }

    function setEngineState(name, val) {
        var idx = engineNames.indexOf(name)
        if (idx < 0) return
        var copy = engineStates.slice()
        copy[idx] = val
        engineStates = copy
    }

    function enabledEnginesList() {
        var out = []
        for (var i = 0; i < engineNames.length; i++)
            if (engineStates[i]) out.push(engineNames[i])
        return out
    }

    // ── Connections ────────────────────────────────────────────────
    Connections {
        target: controller

        function onSearchStarted() {
            allResults = []
            resultsModel.clear()
            resultCount.text = "Searching…"
            searchBtn.enabled = false
            exportBtn.enabled = false
            grabStatus.text = ""
            progressBar.visible = true
            progressBar.value = 0
        }

        function onResultFound(engine, name, size, seeds, leech, link, pubDate) {
            if (!root.isEngineEnabled(engine)) return
            var row = { engine: engine, name: name, size: size,
                        seeds: parseInt(seeds) || 0,
                        leech: parseInt(leech) || 0,
                        link: link,
                        pubDate: parseInt(pubDate) || 0 }
            allResults.push(row)
            rebuildModel()
            resultCount.text = resultsModel.count + " results"
        }

        function onEngineFinished(engine) {
            progressBar.value = Math.min(progressBar.value + (1/6), 1.0)
        }

        function onSearchFinished(total) {
            searchBtn.enabled = true
            exportBtn.enabled = resultsModel.count > 0
            progressBar.visible = false
            resultCount.text = resultsModel.count + " results"
            if (resultsModel.count === 0)
                resultCount.text = "No results found."
        }

        function onDownloadStarted(name) {
            grabStatus.text = "⏳ Downloading: " + name
        }

        function onDownloadDone(path) {
            grabStatus.text = "✔  Saved: " + path
        }

        function onExportDone(path) {
            grabStatus.text = "✔  Exported: " + path
        }

        function onErrorOccurred(msg) {
            grabStatus.text = "⚠  " + msg
            searchBtn.enabled = true
            progressBar.visible = false
        }
    }

    // ── Sort & rebuild ─────────────────────────────────────────────
    function rebuildModel() {
        var arr = allResults.slice()
        arr.sort(function(a, b) {
            var va, vb
            if (sortColumn === 0)      { va = a.pubDate; vb = b.pubDate }
            else if (sortColumn === 1) { va = a.seeds;   vb = b.seeds   }
            else if (sortColumn === 2) { va = a.name.toLowerCase(); vb = b.name.toLowerCase() }
            else                       { va = a.size;    vb = b.size    }
            if (va < vb) return sortAsc ? -1 : 1
            if (va > vb) return sortAsc ?  1 : -1
            return 0
        })
        resultsModel.clear()
        for (var i = 0; i < arr.length; i++) resultsModel.append(arr[i])
    }

    function cycleSort(col) {
        if (sortColumn === col) sortAsc = !sortAsc
        else { sortColumn = col; sortAsc = false }
        rebuildModel()
    }

    function sortIndicator(col) {
        if (sortColumn !== col) return ""
        return sortAsc ? " ▲" : " ▼"
    }

    // ── Layout ─────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Top bar ───────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 72
            color: root.bg2

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 20
                anchors.rightMargin: 20
                spacing: 10

                // Logo
                Column {
                    spacing: 0
                    Label { text: "⚡ TorrentSearch"; font.pixelSize: 20; font.bold: true; color: root.accent }
                    Label { text: "Multi-Engine Aggregator"; font.pixelSize: 10; color: root.muted }
                }

                Item { Layout.fillWidth: true }

                // Search input
                Rectangle {
                    Layout.preferredWidth: 360
                    height: 42
                    radius: 21
                    color: root.bg3
                    border.color: searchField.activeFocus ? root.accent : root.muted
                    border.width: 1.5
                    Behavior on border.color { ColorAnimation { duration: 150 } }

                    TextInput {
                        id: searchField
                        anchors { fill: parent; leftMargin: 18; rightMargin: 44 }
                        color: root.text
                        font.pixelSize: 14
                        verticalAlignment: TextInput.AlignVCenter
                        clip: true
                        Keys.onReturnPressed: doSearch()

                        Label {
                            anchors.fill: parent
                            text: "Search all torrent engines…"
                            color: root.muted
                            font.pixelSize: 14
                            verticalAlignment: Text.AlignVCenter
                            visible: !searchField.text && !searchField.activeFocus
                        }
                    }
                    Label {
                        anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
                        text: "🔍"; font.pixelSize: 16
                        MouseArea { anchors.fill: parent; onClicked: doSearch() }
                    }
                }

                // Category
                ComboBox {
                    id: categoryBox
                    model: ["all","movies","tv","music","games","anime","software","books"]
                    Layout.preferredWidth: 120
                    height: 42
                    background: Rectangle { radius: 21; color: root.bg3; border.color: root.muted; border.width: 1.5 }
                    contentItem: Label { leftPadding: 12; text: categoryBox.displayText; color: root.text; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter }
                }

                // Engines toggle button
                Button {
                    id: engineMenuBtn
                    text: "Engines ▾"
                    height: 42
                    Layout.preferredWidth: 100
                    font.pixelSize: 12
                    background: Rectangle { radius: 21; color: enginePopup.opened ? root.accentD : root.bg3; border.color: root.muted; border.width: 1.5 }
                    contentItem: Label { text: engineMenuBtn.text; color: root.text; font: engineMenuBtn.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    onClicked: enginePopup.opened ? enginePopup.close() : enginePopup.open()
                }

                // Search button
                Button {
                    id: searchBtn
                    text: "Search"
                    height: 42
                    Layout.preferredWidth: 90
                    font.bold: true; font.pixelSize: 13
                    onClicked: doSearch()
                    background: Rectangle {
                        radius: 21
                        color: searchBtn.enabled ? (searchBtn.hovered ? root.accentD : root.accent) : "#1a3a38"
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    contentItem: Label { text: searchBtn.text; color: searchBtn.enabled ? root.bg0 : root.muted; font: searchBtn.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }

                // Export
                Button {
                    id: exportBtn
                    text: "Export TXT"
                    height: 42
                    Layout.preferredWidth: 100
                    enabled: false
                    font.pixelSize: 12
                    onClicked: controller.exportToTxt()
                    background: Rectangle {
                        radius: 21
                        color: exportBtn.enabled ? (exportBtn.hovered ? "#c8941f" : root.gold) : "#2a2a14"
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    contentItem: Label { text: exportBtn.text; color: exportBtn.enabled ? root.bg0 : root.muted; font: exportBtn.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
            }
        }

        // ── Engine popup (proper Popup element) ───────────────────
        Popup {
            id: enginePopup
            parent: Overlay.overlay
            x: root.width - width - 10
            y: 76
            width: 230
            height: contentCol.implicitHeight + 24
            padding: 0
            modal: false
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent

            background: Rectangle {
                color: root.bg2
                border.color: root.accent
                border.width: 1
                radius: 8
            }

            Column {
                id: contentCol
                anchors { fill: parent; margins: 12 }
                spacing: 6
                Label { text: "Enabled Engines"; font.bold: true; color: root.accent; font.pixelSize: 12 }
                Repeater {
                    model: root.engineNames
                    CheckBox {
                        required property string modelData
                        required property int    index
                        text: modelData
                        checked: root.engineStates[index]
                        contentItem: Label {
                            text: parent.text
                            color: root.text
                            font.pixelSize: 12
                            leftPadding: parent.indicator.width + 4
                            verticalAlignment: Text.AlignVCenter
                        }
                        onToggled: root.setEngineState(modelData, checked)
                    }
                }
            }
        }

        // ── Sub-bar ───────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 34
            color: root.bg0

            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 20
                Label { id: resultCount; text: "Enter a query to search all engines"; color: root.textDim; font.pixelSize: 12 }
                Item { Layout.fillWidth: true }
                Label { id: grabStatus; color: root.accent; font.pixelSize: 11; elide: Text.ElideRight; Layout.preferredWidth: 500; horizontalAlignment: Text.AlignRight }
            }
        }

        // ── Progress ──────────────────────────────────────────────
        ProgressBar {
            id: progressBar
            Layout.fillWidth: true
            height: 3
            visible: false
            from: 0; to: 1
            Material.accent: Material.Teal
            background: Item {}
        }

        // ── Column headers ────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 36
            color: "#0b1220"

            RowLayout {
                anchors { fill: parent; leftMargin: 52; rightMargin: 16 }
                spacing: 0

                // Name header
                Item {
                    Layout.fillWidth: true
                    height: parent.height
                    Label {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Name" + sortIndicator(2)
                        color: sortColumn === 2 ? root.accent : root.textDim
                        font.pixelSize: 11; font.bold: true
                    }
                    MouseArea { anchors.fill: parent; onClicked: cycleSort(2) }
                }
                Item { Layout.preferredWidth: 100; height: parent.height
                    Label { anchors.centerIn: parent; text: "Size"; color: root.textDim; font.pixelSize: 11; font.bold: true }
                }
                Item { Layout.preferredWidth: 80; height: parent.height
                    Label { anchors.centerIn: parent; text: "Seeds" + sortIndicator(1); color: sortColumn === 1 ? root.accent : root.textDim; font.pixelSize: 11; font.bold: true }
                    MouseArea { anchors.fill: parent; onClicked: cycleSort(1) }
                }
                Item { Layout.preferredWidth: 80; height: parent.height
                    Label { anchors.centerIn: parent; text: "Date" + sortIndicator(0); color: sortColumn === 0 ? root.accent : root.textDim; font.pixelSize: 11; font.bold: true }
                    MouseArea { anchors.fill: parent; onClicked: cycleSort(0) }
                }
                Item { Layout.preferredWidth: 110; height: parent.height
                    Label { anchors.centerIn: parent; text: "Engine"; color: root.textDim; font.pixelSize: 11; font.bold: true }
                }
                Item { Layout.preferredWidth: 100; height: parent.height }
            }
        }

        // ── Results list ──────────────────────────────────────────
        ListView {
            id: resultsList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: resultsModel
            clip: true
            cacheBuffer: 400

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                contentItem: Rectangle { radius: 3; color: root.accent; opacity: 0.5 }
            }

            Label {
                anchors.centerIn: parent
                visible: resultsModel.count === 0 && !progressBar.visible
                text: "⚡\nSearch across 6 torrent engines\nat once — just type above!"
                horizontalAlignment: Text.AlignHCenter
                color: root.muted; font.pixelSize: 16; lineHeight: 1.7
            }

            delegate: Item {
                id: rowItem
                width: resultsList.width
                height: rowExpanded ? 108 : 56
                property bool rowExpanded: false
                // Cache model data locally so nested items can always access it
                property string rowName:   model.name
                property string rowLink:   model.link
                property string rowEngine: model.engine
                property string rowSize:   model.size
                property int    rowSeeds:  model.seeds
                property int    rowLeech:  model.leech
                property int    rowDate:   model.pubDate

                Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutQuad } }

                // Row BG
                Rectangle {
                    anchors.fill: parent
                    color: index % 2 === 0 ? root.bg1 : root.bg0
                    opacity: rowMouse.containsMouse ? 1.0 : 0.95
                }

                // Accent strip
                Rectangle {
                    anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                    width: rowMouse.containsMouse || rowItem.rowExpanded ? 4 : 0
                    color: engineColor(rowItem.rowEngine)
                    Behavior on width { NumberAnimation { duration: 130 } }
                }

                // ── Mouse area only over the top 56px header (not the buttons) ──
                MouseArea {
                    id: rowMouse
                    anchors { left: parent.left; right: parent.right; top: parent.top }
                    height: 56
                    hoverEnabled: true
                    onClicked: rowItem.rowExpanded = !rowItem.rowExpanded
                }

                // Main row content (z:1 so it renders above MouseArea but still passes through hovers)
                RowLayout {
                    id: mainRow
                    anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 52; rightMargin: 16 }
                    height: 56
                    spacing: 0
                    z: 1

                    // Expand chevron
                    Label {
                        Layout.preferredWidth: 0
                        anchors.left: parent.left
                        anchors.leftMargin: -36
                        anchors.verticalCenter: parent.verticalCenter
                        text: rowItem.rowExpanded ? "▾" : "▸"
                        color: root.textDim
                        font.pixelSize: 14
                    }

                    // Name + subtitle
                    Column {
                        Layout.fillWidth: true
                        spacing: 2
                        anchors.verticalCenter: parent.verticalCenter
                        Label {
                            width: parent.width
                            text: rowItem.rowName
                            color: rowMouse.containsMouse ? engineColor(rowItem.rowEngine) : root.text
                            font.pixelSize: 13; font.bold: true
                            elide: Text.ElideRight
                            Behavior on color { ColorAnimation { duration: 100 } }
                        }
                        Label {
                            width: parent.width
                            text: rowItem.rowLink
                            color: root.muted; font.pixelSize: 9
                            elide: Text.ElideRight
                        }
                    }

                    Label {
                        text: rowItem.rowSize
                        color: root.textDim; font.pixelSize: 12
                        Layout.preferredWidth: 100
                        horizontalAlignment: Text.AlignHCenter
                    }

                    // Seeds badge
                    Rectangle {
                        Layout.preferredWidth: 80; height: 24; radius: 12
                        color: seedColor(rowItem.rowSeeds)
                        Label {
                            anchors.centerIn: parent
                            text: "▲ " + rowItem.rowSeeds
                            color: seedTextColor(rowItem.rowSeeds)
                            font.pixelSize: 11; font.bold: true
                        }
                    }

                    // Date
                    Label {
                        text: formatDate(rowItem.rowDate)
                        color: root.textDim; font.pixelSize: 11
                        Layout.preferredWidth: 80
                        horizontalAlignment: Text.AlignHCenter
                    }

                    // Engine badge
                    Rectangle {
                        Layout.preferredWidth: 110; height: 22; radius: 11
                        color: Qt.darker(engineColor(rowItem.rowEngine), 3)
                        Label {
                            anchors.centerIn: parent
                            text: rowItem.rowEngine
                            color: engineColor(rowItem.rowEngine)
                            font.pixelSize: 10; font.bold: true
                        }
                    }

                    // Placeholder
                    Item { Layout.preferredWidth: 100 }
                }

                // ── Expanded action row (z:2 — above MouseArea, fully clickable) ──
                RowLayout {
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 56; rightMargin: 16; bottomMargin: 10 }
                    height: 36
                    visible: rowItem.rowExpanded
                    opacity: rowItem.rowExpanded ? 1 : 0
                    z: 2
                    Behavior on opacity { NumberAnimation { duration: 150 } }
                    spacing: 10

                    Button {
                        id: grabBtn
                        text: "⬇  Grab .torrent"
                        height: 30
                        Layout.preferredWidth: 150
                        font.pixelSize: 11
                        background: Rectangle { radius: 15; color: grabBtn.hovered ? root.accentD : root.accent }
                        contentItem: Label { text: grabBtn.text; color: root.bg0; font: grabBtn.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                        onClicked: {
                            controller.grabTorrent(rowItem.rowName, rowItem.rowLink)
                        }
                    }

                    Button {
                        id: openBtn
                        text: "🌐  Open in browser"
                        height: 30
                        Layout.preferredWidth: 150
                        font.pixelSize: 11
                        background: Rectangle { radius: 15; color: openBtn.hovered ? root.bg3 : root.bg2; border.color: root.muted; border.width: 1 }
                        contentItem: Label { text: openBtn.text; color: root.text; font: openBtn.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                        onClicked: {
                            // For magnet links open directly (launches torrent client)
                            // For http links open in browser
                            Qt.openUrlExternally(rowItem.rowLink)
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Label {
                        text: "Leech: " + rowItem.rowLeech
                        color: root.pink; font.pixelSize: 11
                    }
                }

                // Divider
                Rectangle {
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: 1; color: "#0d1a2a"
                }
            }
        }

        // ── Footer ────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 28
            color: "#060a10"
            Label {
                anchors.centerIn: parent
                text: "TorrentSearch  •  6 Engines  •  Click any row to expand  •  Sort by clicking column headers"
                color: "#222f40"; font.pixelSize: 10
            }
        }
    }

    // ── Helper functions ───────────────────────────────────────────
    function doSearch() {
        var q = searchField.text.trim()
        if (!q) { grabStatus.text = "Please enter a search term."; return }
        controller.startSearch(q, categoryBox.currentText, root.enabledEnginesList())
    }

    function engineColor(engine) {
        var colors = {
            "LimeTorrents":  "#4ecdc4",
            "PirateBay":     "#ff6b6b",
            "EZTV":          "#a29bfe",
            "TorLock":       "#ffeaa7",
            "SolidTorrents": "#55efc4",
            "TorrentsCSV":   "#fd79a8"
        }
        return colors[engine] || "#4ecdc4"
    }

    function seedColor(seeds) {
        if (seeds > 500) return "#0d2e1a"
        if (seeds > 100) return "#132614"
        if (seeds > 10)  return "#1e2a10"
        return "#2a1010"
    }

    function seedTextColor(seeds) {
        if (seeds > 500) return "#50fa7b"
        if (seeds > 100) return "#8be9fd"
        if (seeds > 10)  return "#f1fa8c"
        return "#ff5555"
    }

    function formatDate(ts) {
        if (!ts || ts <= 0) return "—"
        var d = new Date(ts * 1000)
        return (d.getFullYear()) + "-" +
               String(d.getMonth()+1).padStart(2,"0") + "-" +
               String(d.getDate()).padStart(2,"0")
    }
}

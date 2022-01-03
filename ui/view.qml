import QtQuick 2.9
import QtQuick.Layouts 1.12
import QtQuick.Controls 2.12
import QtQuick.Window 2.12
import QtQuick.Controls.Material 2.12

ApplicationWindow {
    id: ui
    visibility: "Maximized"
    visible: true
    title: qsTr("DoltK")

    Row {
        id: commit_history
        anchors.fill: parent
        anchors.margins: vbar.width

        ListView {
            objectName: "commit_messages"
            width: parent.width / 2
            height: parent.height / 3
            model: history_model
            delegate: Text {
                width: parent.width
                text: model.message
                elide: Text.ElideRight
                font.pixelSize: 15
            }
            ScrollBar.vertical: vbar
        }

        ListView {
            objectName: "commit_authors"
            width: parent.width / 4
            height: parent.height / 3
            model: history_model
            delegate: Text {
                width: parent.width
                text: model.author
                clip: true
                font.pixelSize: 15
            }
            ScrollBar.vertical: vbar
        }

        ListView {
            objectName: "commit_timestamps"
            width: parent.width / 4
            height: parent.height / 3
            model: history_model
            delegate: Text {
                width: parent.width
                text: model.timestamp
                clip: true
                font.pixelSize: 15
            }
            ScrollBar.vertical: vbar
        }
    }

    ScrollBar {
        id: vbar
        height: parent.height / 3
        anchors.right: parent.right
        policy: ScrollBar.AlwaysOn
    }
}

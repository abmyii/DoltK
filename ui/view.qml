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
        anchors.fill: parent
        anchors.margins: vbar.width

        ListView {
            objectName: "commit_messages"
            width: parent.width / 2
            height: parent.height
            model: history_model
            delegate: Text {
                text: display
            }

            ScrollBar.vertical: vbar
        }

        ListView {
            objectName: "commit_authors"
            width: parent.width / 2
            height: parent.height
            model: history_model
            delegate: ItemDelegate {
                width: parent.width
            }
            ScrollBar.vertical: vbar
        }
    }

    ScrollBar {
        id: vbar
        height: parent.height
        anchors.right: parent.right
        policy: ScrollBar.AlwaysOn
    }
}

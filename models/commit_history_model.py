from PyQt5 import QtCore, QtGui


class CommitHistoryModel(QtCore.QAbstractTableModel):
    icons = []
    history = []

    def load_commits(self, repo):
        self.history = list(repo.log().values())
        self.generate_icons()

    def generate_icons(self):
        for commit in self.history:
            icon = QtGui.QPixmap(16, 16)
            icon.fill(QtCore.Qt.transparent)

            painter = QtGui.QPainter(icon)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setBrush(QtCore.Qt.red)
            painter.drawEllipse(QtCore.QPoint(8, 8), 5, 5)

            # if has a parent, add line to parent
            if True:  # parent
                painter.drawLine(8, 12, 8, 20)
                painter.drawLine(8, 4, 8, -4)

            self.icons.append(icon)

    def data(self, index, role):
        commit = self.history[index.row()]

        if role == QtCore.Qt.DisplayRole:
            return {
                0: commit.message.replace('\n', ' '),
                1: f"{commit.author} <{commit.email}>",
                2: commit.timestamp
            }[index.column()]
        elif index.column() == 0 and role == QtCore.Qt.DecorationRole:
            return self.icons[index.row()]

    def rowCount(self, index):
        return len(self.history)

    def columnCount(self, index):
        return 3

import sys

from doltpy.cli import Dolt
from Qt import QtWidgets, QtCompat, QtCore


class CommitHistoryModel(QtCore.QAbstractListModel):
    history = []

    def load_commits(self, repo):
        self.history = list(repo.log().values())

    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:
            text = self.history[index.row()].ref
            return text

    def rowCount(self, index):
        return len(self.history)


class MainWindow:
    def __init__(self):
        # Load repo
        repo = Dolt('.' if len(sys.argv) < 2 else sys.argv[1])
        history = repo.log()

        # Load UI
        app = QtWidgets.QApplication(sys.argv)
        self.ui = QtCompat.loadUi('ui/mainwindow.ui')

        # Create commit history model
        self.history_model = CommitHistoryModel()
        self.history_model.load_commits(repo)
        self.ui.commit_history.setModel(self.history_model)

        # Execute
        self.ui.show()
        sys.exit(app.exec_())
    

if __name__ == '__main__':
    MainWindow()

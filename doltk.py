import sys

from doltpy.cli import Dolt
from Qt import QtWidgets, QtCompat, QtCore


class CommitHistoryModel(QtCore.QAbstractTableModel):
    history = []

    def load_commits(self, repo):
        self.history = list(repo.log().values())

    def data(self, index, role):
        commit = self.history[index.row()]
       
        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0: return commit.message.replace('\n', ' ')
            if index.column() == 1: return f"{commit.author} <{commit.email}>"
            if index.column() == 2: return commit.timestamp.split('.')[0]

    def rowCount(self, index):
        return len(self.history)
    
    def columnCount(self, index):
        return 3


class MainWindow:
    def __init__(self):
        # Load repo
        repo = Dolt('.' if len(sys.argv) < 2 else sys.argv[1])
        history = repo.log()

        # Load UI
        app = QtWidgets.QApplication(sys.argv)
        self.ui = QtCompat.loadUi('ui/mainwindow.ui')

        # Create commit history model
        self.commit_views = [self.ui.commit_messages, self.ui.commit_authors, self.ui.commit_timestamps]

        self.history_model = CommitHistoryModel()
        self.history_model.load_commits(repo)

        for index, view in enumerate(self.commit_views):
            view.setModel(self.history_model)
            view.setModelColumn(index)

        # Execute
        self.ui.showMaximized()
        sys.exit(app.exec_())
    

if __name__ == '__main__':
    MainWindow()

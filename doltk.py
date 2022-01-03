import sys
from os.path import abspath, dirname, join

from doltpy.cli import Dolt
from Qt5 import QtCore, QtQml, QtGui


class CommitHistoryModel(QtCore.QAbstractTableModel):
    history = []

    def load_commits(self, repo):
        self.history = list(repo.log().values())

    def data(self, index, role):
        commit = self.history[index.row()]
       
        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0: return commit.message.replace('\n', ' ')
            if index.column() == 1: return f"{commit.author} <{commit.email}>"
            if index.column() == 2: return commit.timestamp.split('.')[0].split(' +')[0]

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
        app = QtGui.QGuiApplication(sys.argv)
        engine = QtQml.QQmlApplicationEngine()
        context = engine.rootContext()

        # Create commit history model
        self.history_model = CommitHistoryModel()
        self.history_model.load_commits(repo)

        # Expose the Python object to QML
        context.setContextProperty("history_model", self.history_model)

        # Load QML 
        qmlFile = join(dirname(__file__), 'ui', 'view.qml')
        engine.load('ui/view.qml')

        # Execute
        sys.exit(app.exec_())


if __name__ == '__main__':
    MainWindow()

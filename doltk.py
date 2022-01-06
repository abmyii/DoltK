import random
import subprocess
import sys
import time

from doltpy.cli import Dolt
from doltpy.sql import DoltSQLServerContext, DoltSQLEngineContext, ServerConfig
from Qt import QtWidgets, QtCompat, QtCore


def start_sql_server(db_path):
    port = f"{random.randint(1025, 65535)}"
    sql_server = subprocess.Popen(args=["dolt", "sql-server", "--port", port], cwd=db_path)
    time.sleep(1)
    if sql_server.poll():
        print('SQL server terminated - restarting')
        return start_sql_server(db_path)
    return port


class CommitHistoryModel(QtCore.QAbstractTableModel):
    history = []

    def load_commits(self, conn):
        self.history = list(conn.log().values())

    def data(self, index, role):
        commit = self.history[index.row()]
       
        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0: return commit.message.replace('\n', ' ')
            if index.column() == 1: return f"{commit.author} <{commit.email}>"
            if index.column() == 2: return commit.timestamp.strftime('%Y-%m-%d %H:%M:%S')

    def rowCount(self, index):
        return len(self.history)
    
    def columnCount(self, index):
        return 3


class MainWindow:
    def __init__(self):
        # Load repo
        db_path = '.' if len(sys.argv) < 2 else sys.argv[1]
        repo = Dolt(db_path) 

        # Initialse SQL server and connection
        port = start_sql_server(db_path)
        conf = ServerConfig(user="root", host="localhost", port=port)
        conn = DoltSQLEngineContext(repo, conf)

        # Load UI
        app = QtWidgets.QApplication(sys.argv)
        self.ui = QtCompat.loadUi('ui/mainwindow.ui')

        # Create commit history model
        self.commit_views = [self.ui.commit_messages, self.ui.commit_authors, self.ui.commit_timestamps]

        self.history_model = CommitHistoryModel()
        self.history_model.load_commits(conn)

        for index, view in enumerate(self.commit_views):
            view.setModel(self.history_model)
            view.setModelColumn(index)
            view.selectionModel().currentChanged.connect(self.on_row_changed)
            view.verticalScrollBar().valueChanged.connect(self.sync_listviews)

        # Execute
        self.ui.showMaximized()
        sys.exit(app.exec_())

    def on_row_changed(self, current, previous):
        for index, view in enumerate(self.commit_views):
            model_index = self.history_model.index(current.row(), index)
            view.scrollTo(model_index)
            view.setCurrentIndex(model_index)

    def sync_listviews(self, pos):
        for view in self.commit_views:
            view.verticalScrollBar().setValue(pos)


if __name__ == '__main__':
    MainWindow()

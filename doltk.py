import os
import random
import subprocess
import sys
import time

from doltpy.cli import Dolt
from doltpy.sql import DoltSQLEngineContext, ServerConfig
from Qt import QtWidgets, QtCompat, QtCore


def start_sql_server(db_path):
    port = f"{random.randint(1025, 65535)}"
    cmd = f"dolt sql-server -r -l fatal --port {port}"

    sql_server = subprocess.Popen(args=cmd.split(), cwd=db_path)
    time.sleep(1)

    if sql_server.poll():
        print('SQL server terminated - restarting')
        return start_sql_server(db_path)

    return port


class CommitHistoryModel(QtCore.QAbstractTableModel):
    history = []
    current_commit = None

    def load_commits(self, conn):
        self.history = list(conn.log().values())
        self.current_commit = self.history[0]

    def data(self, index, role):
        self.current_commit = self.history[index.row()]

        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0: return self.current_commit.message.replace('\n', ' ')
            if index.column() == 1: return f"{self.current_commit.author} <{self.current_commit.email}>"
            if index.column() == 2: return self.current_commit.timestamp.strftime('%Y-%m-%d %H:%M:%S')

    def rowCount(self, index):
        return len(self.history)

    def columnCount(self, index):
        return 3


class DiffModel(QtCore.QAbstractTableModel):
    diff = {}
    current_table = None

    def __init__(self, vertical_header_height, *args, **kwargs):
        self.vertical_header_height = vertical_header_height
        super().__init__(*args, **kwargs)

    @property
    def tables(self):
        return list(self.diff.keys())

    def load_diff(self, conn, commit):
        self.diff = conn.diff(commit.parents, commit.ref, conn.tables())
        self.diff = {table: df for table, df in self.diff.items() if len(df)}  # Exclude tables without diffs
        self.current_table = list(self.diff)[0]
        print(self.current_table)

    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:
            return str(self.diff[self.current_table].iloc[index.row()].iloc[index.column()])

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Orientation.Vertical:
            return section
        elif orientation == QtCore.Qt.Orientation.Horizontal:
            column = self.diff[self.current_table].columns[section]

            if role == QtCore.Qt.DisplayRole:
                return column
            elif role == QtCore.Qt.SizeHintRole:
                # https://stackoverflow.com/a/46142682
                max_len = self.diff[self.current_table][column].astype(str).str.len().max()
                width = max(len(column), max_len)*10  # 10 is font-size?
                #print(column, width)
                size = QtCore.QSize(width, self.vertical_header_height)
                return size

    def rowCount(self, index):
        return len(self.diff[self.current_table])

    def columnCount(self, index):
        return len(self.diff[self.current_table].columns)


class DiffModelTables(QtCore.QAbstractListModel):

    def __init__(self, diff_model, *args, **kwargs):
        self.diff_model = diff_model
        super().__init__(*args, **kwargs)

    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:
            return self.diff_model.tables[index.row()]

    def rowCount(self, index):
        return len(self.diff_model.tables)


class MainWindow:
    def __init__(self):
        # Load repo
        db_path = os.path.normpath('.' if len(sys.argv) < 2 else sys.argv[1])
        repo = Dolt(db_path)

        # Initialse SQL server and connection
        port = start_sql_server(db_path)
        conf = ServerConfig(user="root", host="localhost", port=port)
        self.conn = DoltSQLEngineContext(repo, conf)

        # Load UI
        app = QtWidgets.QApplication(sys.argv)
        self.ui = QtCompat.loadUi('ui/mainwindow.ui')

        # Create commit history model
        self.commit_views = [self.ui.commit_messages, self.ui.commit_authors, self.ui.commit_timestamps]

        self.history_model = CommitHistoryModel()
        self.history_model.load_commits(self.conn)

        for index, view in enumerate(self.commit_views):
            view.setModel(self.history_model)
            view.setModelColumn(index)
            view.selectionModel().currentChanged.connect(self.on_row_changed)
            view.verticalScrollBar().valueChanged.connect(self.sync_listviews)

        # Create diff model
        self.diff_model = DiffModel(self.ui.diff.verticalHeader().defaultSectionSize())
        self.diff_model.load_diff(self.conn, self.history_model.current_commit)

        self.ui.diff.setModel(self.diff_model)
        self.ui.diff.setColumnWidth(0, 60)
        self.ui.diff.resizeColumnsToContents()

        self.diff_model_tables = DiffModelTables(self.diff_model)
        self.ui.tables.setModel(self.diff_model_tables)
        #self.ui.diff.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        #self.ui.diff.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

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

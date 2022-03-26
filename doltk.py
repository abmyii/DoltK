import os
import pandas as pd
import random
import subprocess
import sys
import time
import warnings

# Surpress UserWarning regarding ordering by null columns (sqlakeyset)
warnings.filterwarnings("ignore")

from doltpy.cli import Dolt
from doltpy.sql import DoltSQLEngineContext, ServerConfig
from sqlakeyset import get_page, select_page
from sqlalchemy import select, text, MetaData, Table
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import literal_column
from Qt import QtWidgets, QtCompat, QtCore


PAGE_SIZE = 1#0000


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

    def __init__(self, vertical_header_height, table_list, *args, **kwargs):
        self.vertical_header_height = vertical_header_height
        self.table_list = table_list
        super().__init__(*args, **kwargs)

    def load_diff(self, conn, commit):
        diff_table = Table('dolt_diff_hospitals', conn.metadata, autoload_with=conn.engine)
        # Order by to_<pk> for pk in pks because from can be null (e.g. adding new row)
        # What about removed, though?
        # Removed - use from
        # Added/modified - use to

        #query = conn.session.query(diff_table).where(text(f'from_commit="{commit.parents}" AND to_commit="{commit.ref}"'))
        query = conn.session.query(diff_table).where(text(f'from_commit="1mj3g3iqk1m8do0u495j3fnif60133p7" AND to_commit="uri5bv8oasoq7ipcku26nnk9h94n0juq"')).order_by(literal_column('to_cms_certification_num'))
        #.order_by(text(', '.join(diff_table.columns.keys())))

        # gets the first page
        print(query.statement)
        page1 = get_page(query, per_page=2)
        page2 = get_page(query, per_page=2, page=page1.paging.next)
        import pdb; pdb.set_trace()
        print(page1)
        print(pd.DataFrame(page1, columns=diff_table.columns.keys()))
        self.diff = conn.diff(commit.parents, commit.ref, conn.tables())
        self.diff = {table: df for table, df in self.diff.items() if len(df)}  # Exclude tables without diffs

        self.current_table = list(self.diff)[0]
        print(self.current_table)

        self.table_list.clear()
        self.table_list.addItems(list(self.diff))
        self.table_list.setCurrentRow(0)

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


class MainWindow:
    def __init__(self):
        # Load repo
        db_path = os.path.normpath('.' if len(sys.argv) < 2 else sys.argv[1])
        repo = Dolt(db_path)

        # Initialse SQL server and connection
        port = start_sql_server(db_path)
        conf = ServerConfig(user="root", host="localhost", port=port)
        self.conn = DoltSQLEngineContext(repo, conf)
        
        # SQLAlchemy setup
        self.conn.session = Session(self.conn.engine)
        self.conn.metadata = MetaData(bind=None)

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
        self.diff_model = DiffModel(self.ui.diff.verticalHeader().defaultSectionSize(), self.ui.tables)
        self.diff_model.load_diff(self.conn, self.history_model.current_commit)

        self.ui.diff.setModel(self.diff_model)
        self.ui.diff.setColumnWidth(0, 60)
        self.ui.diff.resizeColumnsToContents()

        self.ui.tables.currentItemChanged.connect(self.select_table)
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

    def select_table(self, selection):
        self.diff_model.beginResetModel()

        # Update to new table
        self.diff_model.current_table = selection.text()

        self.diff_model.endResetModel()


if __name__ == '__main__':
    MainWindow()

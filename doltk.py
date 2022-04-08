import os
import pandas as pd
import random
import subprocess
import sys
import time

from doltpy.cli import Dolt
from doltpy.cli.read import read_table_sql
from Qt import QtWidgets, QtCompat, QtCore


CHUNKSIZE = 10000
PKs = ['cms_certification_num', 'payer', 'code', 'internal_revenue_code', 'inpatient_outpatient']


# Overrides doltcli.utils.parse_to_pandas since it converts strings to ints
def parse_to_pandas(sql_output):
    return pd.read_csv(sql_output, dtype={column: str for column in PKs})


def get_diff_chunks(repo, table, commit):
    query = f'SELECT * FROM dolt_diff_{table} WHERE from_commit="{commit.parents}" and to_commit="{commit.ref}" LIMIT {CHUNKSIZE};'
    df = read_table_sql(repo, query, result_parser=parse_to_pandas)
    return df 


class CommitHistoryModel(QtCore.QAbstractTableModel):
    history = []
    current_commit = None

    def load_commits(self, repo):
        self.history = list(repo.log().values())
        self.current_commit = self.history[0]

    def data(self, index, role):
        self.current_commit = self.history[index.row()]

        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0: return self.current_commit.message.replace('\n', ' ')
            if index.column() == 1: return f"{self.current_commit.author} <{self.current_commit.email}>"
            if index.column() == 2: return self.current_commit.timestamp#.strftime('%Y-%m-%d %H:%M:%S')

    def rowCount(self, index):
        return len(self.history)

    def columnCount(self, index):
        return 3


class DiffModel(QtCore.QAbstractTableModel):
    diff = {}
    current_table = None

    def __init__(self, repo, vertical_header_height, table_list, *args, **kwargs):
        # FIXME: Only reads once for entire repo - very slow (~3s)
        self.tables = repo.ls()

        self.vertical_header_height = vertical_header_height
        self.table_list = table_list
        super().__init__(*args, **kwargs)

    def load_diff(self, repo, commit):
        # Read first 10k - then only load when scrolling halfway / near end of chunk
        self.diff = {table.name: get_diff_chunks(repo, table.name, commit) for table in self.tables}

        self.current_table = list(self.diff)[0]

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
        if not self.current_table:
            return 0
        return len(self.diff[self.current_table])

    def columnCount(self, index):
        if not self.current_table:
            return 0
        return len(self.diff[self.current_table].columns)


class MainWindow:
    def __init__(self):
        # Load repo
        db_path = os.path.normpath('.' if len(sys.argv) < 2 else sys.argv[1])
        self.repo = Dolt(db_path)

        # Load UI
        app = QtWidgets.QApplication(sys.argv)
        self.ui = QtCompat.loadUi('ui/mainwindow.ui')

        # Create commit history model
        self.commit_views = [self.ui.commit_messages, self.ui.commit_authors, self.ui.commit_timestamps]

        self.history_model = CommitHistoryModel()
        self.history_model.load_commits(self.repo)

        for index, view in enumerate(self.commit_views):
            view.setModel(self.history_model)
            view.setModelColumn(index)
            view.selectionModel().currentChanged.connect(self.on_row_changed)
            view.verticalScrollBar().valueChanged.connect(self.sync_listviews)

        # Create diff model
        self.diff_model = DiffModel(self.repo, self.ui.diff.verticalHeader().defaultSectionSize(), self.ui.tables)

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

            # Disable/re-enable signal so we don't trigger on_row_changed again for each view
            view.selectionModel().currentChanged.disconnect(self.on_row_changed)
            view.scrollTo(model_index)
            view.setCurrentIndex(model_index)
            view.selectionModel().currentChanged.connect(self.on_row_changed)

        # Load new diff
        self.diff_model.beginResetModel() 
        self.diff_model.load_diff(self.repo, self.history_model.current_commit)
        self.diff_model.endResetModel()

    def sync_listviews(self, pos):
        for view in self.commit_views:
            view.verticalScrollBar().setValue(pos)

    def select_table(self, selection):
        if selection:
            self.diff_model.beginResetModel() 
            self.diff_model.current_table = selection.text()  # Update to new table
            self.diff_model.endResetModel()


if __name__ == '__main__':
    MainWindow()

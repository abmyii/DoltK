import os
import pandas as pd
import random
import subprocess
import sys
import time

from doltpy.cli import Dolt
from doltpy.cli.read import read_table_sql
from Qt import QtWidgets, QtCompat, QtCore, QtGui


# NOTE: https://www.dolthub.com/blog/2022-03-25-dolt-diff-magic/


CHUNKSIZE = 1000#0


# Overrides doltcli.utils.parse_to_pandas since it converts strings to ints
def parse_to_pandas(sql_output):
    return pd.read_csv(sql_output, dtype=str)


def get_diff_chunks(repo, table, commit):
    query = f'SELECT * FROM dolt_diff_{table} WHERE from_commit="{commit.parents}" and to_commit="{commit.ref}" LIMIT {CHUNKSIZE};'
    df = read_table_sql(repo, query, result_parser=parse_to_pandas)

    # Remove commit info columns
    df = df.drop(df.filter(regex='^(from|to)_commit(_date)*$').columns, axis=1)

    # Get table PKs
    table_columns = read_table_sql(repo, f'DESC {table};', result_parser=parse_to_pandas)
    table_pks = list(table_columns[table_columns['Key'] == 'PRI']['Field'])

    # Combine from/to columns into one
    columns = [
        (col, f"from_{col}", f"to_{col}")
        for col in df.columns.str.extract('^to_(.*)', expand=False).dropna()
    ]
    for col, from_col, to_col in columns:
        df[col] = df[to_col]
        df.loc[df['diff_type'] == 'removed', col] = df[from_col]  # For removed rows, to_col is NaN

    # Sort on to_<pk> for all PKs
    df = df.sort_values(table_pks)

    # Add modified overlay - each cell will be a list with two values: [before, after]
    # NOTE: This is done after sorting as it fails on list values
    modified = df['diff_type'] == 'modified'
    for col, from_col, to_col in columns:
        df.loc[modified, col] = df[[from_col, to_col]].agg(list, axis=1)

    df.loc[modified, 'diff_type'] = 'modified_from'
    df = df.append(df.loc[modified].assign(diff_type='modified_to')).sort_index().reset_index(drop=True)  # Insert rows directly below original modified row

    # Drop from/to columns and reorder so diff_type is at the end
    df.drop(df.filter(regex='^(from|to)').columns, axis=1, inplace=True)
    df.insert(len(df.columns)-1, 'diff_type', df.pop('diff_type'))

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
        row = self.diff[self.current_table].iloc[index.row()]
        value = row.iloc[index.column()]
        isna = pd.isna(value) is True
        if role == QtCore.Qt.FontRole:
            font = QtGui.QFont("Courier New")
            font.setStyleHint(QtGui.QFont.Monospace)  # https://stackoverflow.com/a/42042184
            return font
        elif role == QtCore.Qt.DisplayRole:
            if isna:
                return 'NaN'
            elif row['diff_type'].startswith('modified'):
                return str(value[0 if row['diff_type'] == 'modified_from' else 1])
            else:
                return str(value)
        elif role == QtCore.Qt.ForegroundRole:
            if isna:
                return QtGui.QColor(149, 163, 167, 125)
            elif row['diff_type'] == 'added':
                return QtGui.QColor('#5AC58D')
            elif row['diff_type'] == 'removed':
                return QtGui.QColor('#FF9A99')
            elif row['diff_type'] == 'modified_from' and len(set(value)) == 2:  # If both values for column are the same, then it is unmodified
                return QtGui.QColor('#FF9A99')
            elif row['diff_type'] == 'modified_to' and len(set(value)) == 2:
                return QtGui.QColor('#5AC58D')
            else:
                return QtGui.QColor('#95A3A7')
        elif role == QtCore.Qt.BackgroundRole:
            if row['diff_type'] == 'added':
                return QtGui.QColor('#DDFAE3')
            elif row['diff_type'] == 'removed':
                return QtGui.QColor('#FEE9EB')

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Orientation.Horizontal:
            column = self.diff[self.current_table].columns[section]

            if role == QtCore.Qt.DisplayRole:
                return column
            elif role == QtCore.Qt.SizeHintRole:
                # https://stackoverflow.com/a/46142682
                # https://stackoverflow.com/a/27446356 instead?
                max_len = self.diff[self.current_table][column].astype(str).str.len().max()
                width = max(len(column), max_len)*10  # 10 is font-size?
                #print(column, width)
                size = QtCore.QSize(width, self.vertical_header_height)
                return size
        else:
            row = self.diff[self.current_table].iloc[section]
            indicator = '+' if row['diff_type'] in ['added', 'modified_to'] else '−'
            if role == QtCore.Qt.DisplayRole:
                return indicator 
            elif role == QtCore.Qt.ForegroundRole:
                if indicator == '+':
                    return QtGui.QColor('#5AC58D')
                else:
                    return QtGui.QColor('#FF9A99')
            elif role == QtCore.Qt.BackgroundRole:
                if row['diff_type'] == 'added':
                    return QtGui.QColor('#DDFAE3')
                elif row['diff_type'] == 'removed':
                    return QtGui.QColor('#FEE9EB')

    def rowCount(self, index):
        if not self.current_table:
            return 0
        return len(self.diff[self.current_table])

    def columnCount(self, index):
        if not self.current_table:
            return 0
        return len(self.diff[self.current_table].columns)-1  # -1 to exclude diff_type


class FramelessHeaderView(QtWidgets.QHeaderView):

    def paintSection(self, painter, rect, logicalIndex):
        data = self.model().headerData(logicalIndex, self.orientation(), QtCore.Qt.DisplayRole)

        fm = painter.fontMetrics()

        painter.fillRect(rect, QtGui.QBrush(QtGui.QColor("white")))
        painter.drawText(rect, QtCore.Qt.AlignLeft, data)


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
            view.selectionModel().currentChanged.connect(self.on_commit_changed)
            view.verticalScrollBar().valueChanged.connect(self.sync_listviews)

        # Update num_commits
        self.ui.num_commits.setText(str(len(self.history_model.history)))

        # Create diff model
        self.diff_model = DiffModel(self.repo, self.ui.diff.verticalHeader().defaultSectionSize(), self.ui.tables)

        self.ui.diff.setModel(self.diff_model)
        self.ui.diff.setColumnWidth(0, 60)
        self.ui.diff.resizeColumnsToContents()

        self.ui.tables.currentItemChanged.connect(self.select_table)
        #self.ui.diff.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        #self.ui.diff.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.ui.diff.setShowGrid(False)
        #self.ui.diff.setVerticalHeader(FramelessHeaderView(QtCore.Qt.Orientation.Vertical, self.ui.diff))

        # https://stackoverflow.com/a/11456661

        # Make a copy of the current header palette.
        palette = self.ui.diff.verticalHeader().palette()

        # Set the normal/active, background color
        palette.setColor( QtGui.QPalette.Normal, QtGui.QPalette.Window, QtCore.Qt.white );

        # Set the palette on the header.
        self.ui.diff.verticalHeader().setPalette(palette)

        # Execute
        self.ui.showMaximized()
        sys.exit(app.exec_())

    def on_commit_changed(self, current, previous):
        for index, view in enumerate(self.commit_views):
            model_index = self.history_model.index(current.row(), index)

            # Disable/re-enable signal so we don't trigger on_commit_changed again for each view
            view.selectionModel().currentChanged.disconnect(self.on_commit_changed)
            view.scrollTo(model_index)
            view.setCurrentIndex(model_index)
            view.selectionModel().currentChanged.connect(self.on_commit_changed)

        # Load new diff
        self.diff_model.beginResetModel() 
        self.diff_model.load_diff(self.repo, self.history_model.current_commit)
        self.diff_model.endResetModel()

        # Update SHA1
        self.ui.sha_id.setText(self.history_model.current_commit.ref)

        # Update commit number
        self.ui.commit_no.setText(str(current.row()+1))

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

#!/usr/bin/env python3
from doltpy.cli import Dolt
from Qt import QtWidgets, QtCompat, QtCore, QtGui

import os
import sys

from models.diff_model import DiffModel
from models.commit_history_model import CommitHistoryModel


# https://stackoverflow.com/a/39433736
class HorizontalLineDelegate(QtWidgets.QStyledItemDelegate):

    def __init__(self, tableView):
        super().__init__(tableView)

        gridHint = tableView.style().styleHint(
            QtWidgets.QStyle.SH_Table_GridLineColor, QtWidgets.QStyleOptionViewItem()
        )
        gridHint &= 0xffffffff  # https://riverbankcomputing.com/pipermail/pyqt/2010-February/025893.html  # noqa: E501
        gridColor = QtGui.QColor.fromRgb(gridHint)

        self.pen = QtGui.QPen(gridColor, 0, tableView.gridStyle())
        self.view = tableView

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        oldPen = painter.pen()
        painter.setPen(self.pen)

        p1 = QtCore.QPoint(
            option.rect.bottomLeft().x()-1, option.rect.bottomLeft().y()
        )
        p2 = QtCore.QPoint(
            option.rect.bottomRight().x()+1, option.rect.bottomRight().y()
        )
        painter.drawLine(p1, p2)
        painter.setPen(oldPen)


class MainWindow:
    def __init__(self):
        # Load repo
        db_path = os.path.normpath('.' if len(sys.argv) < 2 else sys.argv[1])
        self.repo = Dolt(db_path)

        # Load UI
        app = QtWidgets.QApplication(sys.argv)
        self.ui = QtCompat.loadUi('ui/mainwindow.ui')

        # Create commit history model
        self.commit_views = [
            self.ui.commit_messages, self.ui.commit_authors, self.ui.commit_timestamps
        ]

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
        self.diff_model = DiffModel(
            self.repo,
            self.ui.tables
        )

        self.ui.diff.setModel(self.diff_model)

        # Style diff table grids
        row_delegate = HorizontalLineDelegate(self.ui.diff)
        self.ui.diff.setItemDelegate(row_delegate)
        self.ui.diff.horizontalHeader().setStyleSheet(
            """
            QHeaderView { background-color:white }
            QHeaderView::section {
                border: none;
                border-bottom: 1px solid %s;
                background-color:white
            }
            """ % row_delegate.pen.color().name()
        )
        self.ui.diff.horizontalHeader().setFixedHeight(
            self.ui.diff.verticalHeader().defaultSectionSize()
        )

        # Connect signals
        self.ui.query.returnPressed.connect(
            lambda: self.diff_model.filter_query(
                self.repo, self.history_model.history[0], self.ui.query.text()
            )
        )
        self.ui.tables.currentItemChanged.connect(self.select_table)

        # Execute
        self.ui.showMaximized()
        sys.exit(app.exec_())

    def on_commit_changed(self, current, previous):
        commit = self.history_model.history[current.row()]

        for index, view in enumerate(self.commit_views):
            model_index = self.history_model.index(current.row(), index)

            # Disable/re-enable signal so we don't trigger on_commit_changed
            # again for each view
            view.selectionModel().currentChanged.disconnect(self.on_commit_changed)
            view.scrollTo(model_index)
            view.setCurrentIndex(model_index)
            view.selectionModel().currentChanged.connect(self.on_commit_changed)

        # Load new diff
        self.diff_model.beginResetModel()
        self.diff_model.load_diff(self.repo, commit)
        self.diff_model.endResetModel()

        # Update SHA1
        self.ui.sha_id.setText(commit.ref)

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

            self.resize_diff_columns()

    def resize_diff_columns(self):
        for column in range(self.diff_model.columnCount(None)):
            # First column (symbol for diff_type) should be a little larger
            if column == 0:
                self.ui.diff.setColumnWidth(
                    column,
                    self.ui.diff.horizontalHeader().defaultSectionSize()/2
                )
            else:
                # https://stackoverflow.com/a/27446356
                text = self.diff_model.get_longest_str(column)
                document = QtGui.QTextDocument(text)
                document.setDefaultFont(self.diff_model.font)
                self.ui.diff.setColumnWidth(column, document.idealWidth()*1.5)


if __name__ == '__main__':
    MainWindow()

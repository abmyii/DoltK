import sys

from Qt import QtWidgets, QtCompat


class MainWindow(QtWidgets.QWidget):
    """Load .ui file example, using setattr/getattr approach"""
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.ui = QtCompat.loadUi('ui/mainwindow.ui')


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

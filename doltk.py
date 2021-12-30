import sys

from Qt import QtWidgets, QtCompat


def main():
    app = QtWidgets.QApplication(sys.argv)
    mainwindow = QtCompat.loadUi('ui/mainwindow.ui')
    mainwindow.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

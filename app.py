#!/usr/bin/env python
"""
main program for prototype video player
takes one positional argument: path to video file
"""
import sys
import argparse
from PyQt5 import QtWidgets

from src.ui import MainWindow


def main():
    app = QtWidgets.QApplication(sys.argv)

    main_window = MainWindow()

    parser = argparse.ArgumentParser()

    parser.add_argument('project_dir')
    args = parser.parse_args()

    try:
        #main_window.centralWidget().load_video(args.video_file)
        main_window.open_project(args.project_dir)
    except Exception as e:
        sys.exit(f"Error loading file:  {e}")

    main_window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

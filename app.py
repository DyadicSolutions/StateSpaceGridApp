import sys

from typing import List, Callable

import PySide6.QtWidgets
import PySide6.QtGui

import pandas as pd

import matplotlib.backends.backend_qtagg

import statespacegrid.grid
import statespacegrid.trajectory

def WidgetClass(cls):
    """
    Decorator to hackily extend a widget class's __init__ so that it handles
    all of the necessary plumbing with parent layouts/widgets.
    """
    original_init = cls.__init__
    def new_init(self, parent_widget, *args, **kwargs):
        original_init(self, *args, **kwargs)
        if issubclass(cls, PySide6.QtWidgets.QLayout):
            parent_widget.addLayout(self)
        elif issubclass(cls, PySide6.QtWidgets.QWidget):
            parent_widget.addWidget(self)
    cls.__init__ = new_init
    return cls

@WidgetClass
class TrajectoryListWidget(PySide6.QtWidgets.QScrollArea):
    """
    Widget to show a list of dragged in datafiles
    """
    def __init__(self):
        super().__init__()
        self.inner_widget = PySide6.QtWidgets.QWidget() # This seems sketchy - is it really necessary?
        self.setWidget(self.inner_widget)
        self.vbox = PySide6.QtWidgets.QVBoxLayout()

    def addTrajectory(self, trajectory):
        pass

@WidgetClass
class VariableDropdownWidget(PySide6.QtWidgets.QComboBox):
    """
    Widget for column selection for input variables
    """
    def __init__(self, variable_name, variable_listeners):
        super().__init__()
        self.name = variable_name
        self.contents = set()
        variable_listeners.append(lambda var_list: self.update_dropdown(var_list))

    def update_dropdown(self, var_list):
        update_set = set(var_list) - self.contents
        self.contents = self.contents | update_set
        self.addItems(list(update_set))

@WidgetClass
class TitleWidget(PySide6.QtWidgets.QLabel):
    """
    Text display widget, used to add titles for each of the column dropdowns
    """
    def __init__(self, title):
        super().__init__(title)

@WidgetClass
class GridVariableAssignWidget(PySide6.QtWidgets.QVBoxLayout):
    """
    Widget which holds a title for a dropdown and the dropdown itself in a
    vbox for the column selection
    """
    def __init__(self, variable_name, variable_listeners):
        super().__init__()
        TitleWidget(self, variable_name)
        self.dropdown = VariableDropdownWidget(self, variable_name, variable_listeners)

    @property
    def content(self):
        return self.dropdown.currentText()

@WidgetClass
class RangeListWidget(PySide6.QtWidgets.QLineEdit):
    """
    Text input widget for specifying state ranges on the x and y axes
    """
    def __init__(self):
        super().__init__()
        self.list_content = []
        self.editingFinished.connect(self.updateListContent)

    def updateListContent(self):
        self.list_content = [tick.strip() for tick in self.text().split(",")]

@WidgetClass
class GridRangeAssignWidget(PySide6.QtWidgets.QVBoxLayout):
    """
    Widget which holds a title for a range input widget and the widget itself
    in a vbox for range selection
    """
    def __init__(self, variable_name):
        super().__init__()
        TitleWidget(self, variable_name)
        self.list_widget = RangeListWidget(self)

    @property
    def content(self):
        return self.list_widget.list_content

@WidgetClass
class ActionButtonWidget(PySide6.QtWidgets.QPushButton):
    """
    A "Do Something" button - the "something" specified by the callback "action"
    """
    def __init__(self, name: str, action: Callable[[None], None]):
        super().__init__(name)
        self.setFont(PySide6.QtGui.QFont("Segoe UI", 10))
        self.clicked.connect(action)

@WidgetClass
class OptionsAndInfoWidget(PySide6.QtWidgets.QHBoxLayout):
    """
    Widget to hold all of the column and range select widgets.
    These will apply to _all_ input trajectories
    """
    def __init__(
            self,
            hoisted_delete_func: Callable[[None],None],
            hoisted_plot_func: Callable[[None],None],
            header_listeners: List[Callable[[List[str]], None]]):
        super().__init__()
        # These maybe belong in a scrollable list?
        # Have a single fixed top row - "do for all"
        # Then each actual trajectory has its own lil cell
        self.affect_1 = GridVariableAssignWidget(self, "Affect 1", header_listeners)
        self.affect_2 = GridVariableAssignWidget(self, "Affect 2", header_listeners)
        self.onset = GridVariableAssignWidget(self, "Onset", header_listeners)
        self.x_range = GridRangeAssignWidget(self, "x range")
        self.y_range = GridRangeAssignWidget(self, "y range")
        ActionButtonWidget(self, "Plot", hoisted_plot_func)
        ActionButtonWidget(self, "Delete All", hoisted_delete_func)

@WidgetClass
class SSGWidget(matplotlib.backends.backend_qtagg.FigureCanvasQTAgg):
    """
    Widget to hold the matplotlib plot output from statespacegrid.grid.draw
    """
    def __init__(self):
        self.fig, self.ax = statespacegrid.grid.draw(statespacegrid.trajectory.Trajectory(), display=False)
        super().__init__(self.fig)

    def plot(self, *trajectories):
        for line in self.ax.lines:
            line.remove()
        for patch in self.ax.patches:
            patch.remove()
        statespacegrid.grid.draw(*trajectories, fig=self.fig, ax=self.ax, display=False)
        self.draw()

class AppWindow(PySide6.QtWidgets.QMainWindow):
    """
    Window for StateSpaceGridApp. Serves as a holder for everything else
    """

    def __init__(self):
        super().__init__()
        self.data_headers = set()
        self.header_listeners = []
        self.data = []


        self.setWindowTitle("State Space Grid App")
        self.setMinimumSize(600, 400)
        self.setAcceptDrops(True)

        self.central_widget = PySide6.QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = PySide6.QtWidgets.QVBoxLayout(self.central_widget)

        self.grid = SSGWidget(self.main_layout)
        self.options = OptionsAndInfoWidget(
            self.main_layout,
            hoisted_delete_func=lambda: self.data.clear(),
            hoisted_plot_func=lambda: self.plotAllData(),
            header_listeners=self.header_listeners)
        self.trajectory_list = None # placeholder until we drag a trajectory in

    def plotAllData(self):
        x_range = self.options.x_range.content
        y_range = self.options.y_range.content
        # Update x,y range if nothing else
        self.grid.plot(statespacegrid.trajectory.Trajectory(
            x_range=x_range,
            y_range=y_range)
        )
        affect_1 = self.options.affect_1.content
        affect_2 = self.options.affect_2.content
        onset    = self.options.onset.content
        print(affect_1)
        print(affect_2)
        print(x_range)
        print(y_range)
        print(onset)
        for data in self.data:
            print(list(zip(data[affect_1].dropna().astype(str), data[affect_2].dropna().astype(str))))
        trajectory_list = [
            statespacegrid.trajectory.Trajectory(
                x_range=x_range,
                y_range=y_range,
                states=list(zip(list(data[affect_1].dropna()), list(data[affect_2].dropna()))),
                times=list(data[onset].dropna().astype(float))
            )
            for data in self.data
        ]
        self.grid.plot(*trajectory_list)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().endswith(".csv"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if self.trajectory_list is None:
            self.trajectory_list = TrajectoryListWidget(
                self.main_layout
            )

        if event.mimeData().hasUrls():
            file_path = event.mimeData().urls()[0].toLocalFile()
            if file_path.endswith(".csv"):
                self.load_csv_to_table(file_path)

    def load_csv_to_table(self, file_path):
        data = pd.read_csv(file_path, dtype=str)
        self.data_headers = self.data_headers | set(data.keys())
        self.data.append(data)
        for func in self.header_listeners:
            func(self.data_headers)

if __name__ == "__main__":
    app = PySide6.QtWidgets.QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())
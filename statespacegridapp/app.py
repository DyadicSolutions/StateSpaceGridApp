import sys
import os

from typing import List, Callable

import PySide6.QtCore
import PySide6.QtWidgets
import PySide6.QtGui

import matplotlib.backends.backend_qtagg

import statespacegrid.grid
import statespacegrid.measure
import statespacegrid.trajectory

from statespacegridapp import controller, model


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
class TitleWidget(PySide6.QtWidgets.QLabel):
    """
    Text display widget, used to add titles for more dynamic elements
    """
    def __init__(self, title):
        super().__init__(title)

@WidgetClass
class TrajectoryRowWidget(PySide6.QtWidgets.QWidget):
    """
    Widget to show a single data file in the trajectory list
    """
    def __init__(self, data: model.DataObjectHolder):
        super().__init__()
        print(f"Title: {data.filename}")
        self.interior_layout = PySide6.QtWidgets.QHBoxLayout(self)
        TitleWidget(self.interior_layout, str(data.filename))
        self.interior_layout.addStretch()
        check = PySide6.QtWidgets.QCheckBox()
        check.setChecked(data.selected)
        check.checkStateChanged.connect(lambda new_state: data.setSelected(new_state == PySide6.QtCore.Qt.CheckState.Checked))
        self.interior_layout.addWidget(check)

@WidgetClass
class TrajectoryListWidget(PySide6.QtWidgets.QScrollArea):
    """
    Widget to show a list of dragged in datafiles
    """
    def __init__(self, controller: controller.AppControl):
        super().__init__()
        self.inner_widget = PySide6.QtWidgets.QWidget()

        self.vbox = PySide6.QtWidgets.QVBoxLayout(self.inner_widget)
        self.vbox.setSpacing(0)
        # Note - important to allow dynamic updates after initial construction
        self.setWidgetResizable(True)

        self.inner_widget.setLayout(self.vbox)
        self.setWidget(self.inner_widget)
        self.traj_data_rows = []
        controller.resets.append(self.reset)
        controller.addDataListener(self.updateTrajectories)
        self.controller = controller

    def updateTrajectories(self, trajectory_data_list: List[model.DataObjectHolder]):
        self.reset()
        for traj_data in trajectory_data_list:
            self.traj_data_rows.append(TrajectoryRowWidget(self.vbox, traj_data))

    def reset(self):
        print("reset")
        for row in self.traj_data_rows:
            print("deleting row")
            self.vbox.removeWidget(row)
            row.deleteLater()
        self.traj_data_rows.clear()
        self.vbox.update()

@WidgetClass
class VariableDropdownWidget(PySide6.QtWidgets.QComboBox):
    """
    Widget for column selection for input variables
    """
    def __init__(self, variable_name: str, controller: controller.AppControl, variable_setter: Callable[[str], None], is_optional: bool = False):
        super().__init__()
        self.name = variable_name
        self.contents = set()
        self.currentTextChanged.connect(variable_setter)
        self.is_optional = is_optional
        controller.addDataListener(lambda traj_list: self.update_dropdown([header for traj in traj_list for header in traj.headers]))
        controller.resets.append(self.reset)

    def update_dropdown(self, var_list: List[str]):
        if self.is_optional:
            var_list.insert(0, "")
        update_set = set(var_list) - self.contents
        self.contents = self.contents | update_set
        self.addItems(list(update_set))

    def reset(self):
        self.contents = set()
        self.clear()

@WidgetClass
class GridVariableAssignWidget(PySide6.QtWidgets.QVBoxLayout):
    """
    Widget which holds a title for a dropdown and the dropdown itself in a
    vbox for the column selection
    """
    def __init__(self, variable_name: str, controller: controller.AppControl, variable_setter: Callable[[str], None], is_optional: bool=False):
        super().__init__()
        TitleWidget(self, variable_name)
        self.dropdown = VariableDropdownWidget(self, variable_name, controller, variable_setter, is_optional=is_optional)
        controller.resets.append(self.reset)

    @property
    def content(self):
        return self.dropdown.currentText()

    def reset(self):
        self.dropdown.reset()

@WidgetClass
class RangeListWidget(PySide6.QtWidgets.QLineEdit):
    """
    Text input widget for specifying state ranges on the x and y axes
    """
    def __init__(self, variable_setter: Callable[[str], None]):
        super().__init__()
        self.list_content = []
        self.textChanged.connect(variable_setter)

@WidgetClass
class GridRangeAssignWidget(PySide6.QtWidgets.QVBoxLayout):
    """
    Widget which holds a title for a range input widget and the widget itself
    in a vbox for range selection
    """
    def __init__(self, variable_name: str, variable_setter: Callable[[str], None]):
        super().__init__()
        TitleWidget(self, variable_name)
        self.list_widget = RangeListWidget(self, variable_setter)

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
    Layout to hold all of the column and range select widgets.
    These will apply to _all_ input trajectories
    """
    def __init__(self, controller: controller.AppControl):
        super().__init__()
        self.affect_x = GridVariableAssignWidget(self, "Affect x", controller, controller.state.set_x_header)
        self.affect_y = GridVariableAssignWidget(self, "Affect y", controller, controller.state.set_y_header)
        self.onset = GridVariableAssignWidget(self, "Onset", controller, controller.state.set_t_header)
        self.x_range = GridRangeAssignWidget(self, "x range", controller.state.set_x_range)
        self.y_range = GridRangeAssignWidget(self, "y range", controller.state.set_y_range)
        self.onset = GridVariableAssignWidget(self, "Split by ID", controller, controller.state.addSplitByID, is_optional=True)
        ActionButtonWidget(self, "Plot", controller.plot)
        ActionButtonWidget(self, "Delete All", controller.reset)

@WidgetClass
class ExportToolbar(PySide6.QtWidgets.QHBoxLayout):
    """
    Layout to hold all of the export buttons:
     - grid
     - measures (individual)
     - measures (cumulative)
    """
    def __init__(self, controller: controller.AppControl):
        super().__init__()
        self.control = controller
        button_size_policy = PySide6.QtWidgets.QSizePolicy(
            PySide6.QtWidgets.QSizePolicy.Policy.Minimum,
            PySide6.QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.export_grid_button = ActionButtonWidget(self, "Export Grid", self.save_grid)
        self.export_individual_measures_button = ActionButtonWidget(self, "Export Measures", self.save_individual_measures)
        self.export_cumulative_measures_button = ActionButtonWidget(self, "Export Cumulative Measures", self.save_cumulative_measures)
        self.export_grid_button.setSizePolicy(button_size_policy)
        self.export_individual_measures_button.setSizePolicy(button_size_policy)
        self.export_cumulative_measures_button.setSizePolicy(button_size_policy)
        self.addStretch()

    def save_grid(self):
        path, _ = PySide6.QtWidgets.QFileDialog.getSaveFileName(
            caption = "Save grid",
            filter="PNG File (*.png)")
        if path:
            self.control.export_plot(path)

    def save_individual_measures(self):
        path, _ = PySide6.QtWidgets.QFileDialog.getSaveFileName(
            caption = "Save individual measures",
            filter="CSV File (*.csv)")
        if path:
            self.control.export_measures(path, do_for_individual_trajectories=True)

    def save_cumulative_measures(self):
        path, _ = PySide6.QtWidgets.QFileDialog.getSaveFileName(
            caption = "Save cumulative measures",
            filter="CSV File (*.csv)")
        if path:
            self.control.export_measures(path, do_for_individual_trajectories=False)



@WidgetClass
class SSGWidget(matplotlib.backends.backend_qtagg.FigureCanvasQTAgg):
    """
    Widget to hold the matplotlib plot output from statespacegrid.grid.draw
    """
    def __init__(self, controller: controller.AppControl):
        self.controller = controller
        self.fig, self.ax = statespacegrid.grid.draw(statespacegrid.trajectory.Trajectory(), display=False)
        self.controller.set_plot_structures(self.fig, self.ax)
        self.controller.plot_listener = lambda trajectory_list, x_header, y_header: self.plot(*trajectory_list, x_label=x_header, y_label=y_header)
        self.controller.resets.append(self.reset)
        super().__init__(self.fig)

    def plot(self, *trajectories, x_label=None, y_label=None):
        self.clear()
        if trajectories:
            statespacegrid.grid.draw(*trajectories, fig=self.fig, ax=self.ax, display=False, xlabel=x_label, ylabel=y_label)
        self.draw()

    def clear(self):
        for line in self.ax.lines:
            line.remove()
        for patch in self.ax.patches:
            patch.remove()
        self.ax.set_xlabel("")
        self.ax.set_ylabel("")
        self.draw()

    def reset(self):
        self.clear()


@WidgetClass
class VarWidget(PySide6.QtWidgets.QLabel):
    """
    Text display widget, used for dynamically-changing variables
    Keeping separate from TitleWidget as will probably want to tweak styling later
    """
    def __init__(self, title):
        super().__init__(title)


@WidgetClass
class MeasureWidget(PySide6.QtWidgets.QHBoxLayout):
    """
    Layout for single measure in measures list
    """
    def __init__(self, measure_name: str):
        super().__init__()
        self.measure_name = TitleWidget(self, measure_name)
        self.addStretch()
        self.measure_value = VarWidget(self, "")

    def setMeasureValue(self, value):
        self.measure_value.setText(f"{value:.3f}")


@WidgetClass
class MeasuresWindow(PySide6.QtWidgets.QVBoxLayout):
    """
    List of all the measures for a plot
    """
    def __init__(self, controller: controller.AppControl):
        super().__init__()
        controller.measure_listener = self.setMeasures
        controller.resets.append(self.reset)
        self.mean_trajectory_duration = MeasureWidget(self, "Mean trajectory duration")
        self.mean_number_of_events = MeasureWidget(self, "Mean number of events")
        self.mean_number_of_visits = MeasureWidget(self, "Mean number of visits")
        self.mean_state_range = MeasureWidget(self, "Mean state range")
        self.total_state_range = MeasureWidget(self, "Total state range")
        self.mean_event_duration = MeasureWidget(self, "Mean event duration")
        self.mean_visit_duration = MeasureWidget(self, "Mean visit duration")
        self.mean_state_duration = MeasureWidget(self, "Mean state duration")
        self.mean_dispersion = MeasureWidget(self, "Mean dispersion")

    def setMeasures(self, measures: statespacegrid.measure.Measures):
        self.mean_trajectory_duration.setMeasureValue(measures.mean_trajectory_duration)
        self.mean_number_of_events.setMeasureValue(measures.mean_number_of_events)
        self.mean_number_of_visits.setMeasureValue(measures.mean_number_of_visits)
        self.mean_state_range.setMeasureValue(measures.mean_state_range)
        self.total_state_range.setMeasureValue(measures.total_state_range)
        self.mean_event_duration.setMeasureValue(measures.mean_event_duration)
        self.mean_visit_duration.setMeasureValue(measures.mean_visit_duration)
        self.mean_state_duration.setMeasureValue(measures.mean_state_duration)
        self.mean_dispersion.setMeasureValue(measures.mean_dispersion)

    def reset(self):
        self.mean_trajectory_duration.setMeasureValue(0)
        self.mean_number_of_events.setMeasureValue(0)
        self.mean_number_of_visits.setMeasureValue(0)
        self.mean_state_range.setMeasureValue(0)
        self.total_state_range.setMeasureValue(0)
        self.mean_event_duration.setMeasureValue(0)
        self.mean_visit_duration.setMeasureValue(0)
        self.mean_state_duration.setMeasureValue(0)
        self.mean_dispersion.setMeasureValue(0)


@WidgetClass
class PlotAndMeasures(PySide6.QtWidgets.QHBoxLayout):
    """
    Horizontal layout for SSG plot and measures
    """
    def __init__(self, controller: controller.AppControl):
        super().__init__()
        # TODO - try to add stretches
        self.grid = SSGWidget(self, controller)
        self.measures = MeasuresWindow(self, controller)


class AppWindow(PySide6.QtWidgets.QMainWindow):
    """
    Window for StateSpaceGridApp. Serves as a holder for everything else
    """

    def __init__(self):
        super().__init__()

        self.controller = controller.AppControl()
        self.data_model = self.controller.state


        self.setWindowTitle("State Space Grid App")
        self.setMinimumSize(600, 400)
        self.setAcceptDrops(True)

        self.central_widget = PySide6.QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = PySide6.QtWidgets.QVBoxLayout(self.central_widget)

        self.export_toolbar = ExportToolbar(self.main_layout, self.controller)
        self.grid_and_measures = PlotAndMeasures(self.main_layout, self.controller)
        self.options = OptionsAndInfoWidget(self.main_layout, self.controller)
        self.trajectory_list = None # placeholder until we drag a trajectory in


    def plotAllData(self):
        self.controller.plot()

    def dragEnterEvent(self, event: PySide6.QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if self.controller.canHandle(os.path.splitext(url.toLocalFile())[-1]):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if self.trajectory_list is None:
            self.trajectory_list = TrajectoryListWidget(
                self.main_layout, self.controller
            )

        if event.mimeData().hasUrls():
            for file_path in event.mimeData().urls():
                self.controller.read_file(file_path.toLocalFile())

def main():
    app = PySide6.QtWidgets.QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
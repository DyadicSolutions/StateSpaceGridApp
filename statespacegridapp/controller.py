import inspect
import os
from typing import List, Callable, Optional
from dataclasses import asdict

import pandas as pd
from matplotlib import figure, axes

import statespacegrid.trajectory
import statespacegrid.measure

from statespacegridapp import model

class AppError(Exception):
    def __init__(self, message):
        super().__init__(message)

def file_reader(extension: str):
    def decorator(func):
        func.extension_handler = extension
        return func
    return decorator


class AppControl:

    def __init__(self):
        self.state = model.AppState()
        self.file_readers = {}
        for attr_name in dir(AppControl):
            attr = getattr(self, attr_name)
            if inspect.ismethod(attr) and hasattr(attr, "extension_handler"):
                self.file_readers[attr.extension_handler] = attr
        self.plot_listener: Optional[Callable[[List[statespacegrid.trajectory.Trajectory], str, str]]] = None
        self.measure_listener: Optional[Callable[[statespacegrid.measure.Measures]]] = None
        self.resets: List[Callable[[], None]] = []

    def plot(self):
        trajectories = self.getTrajectories()
        if self.plot_listener is None:
            raise AppError("Problem with app generation - no associated plot function for plot display")
        self.plot_listener(trajectories, self.state.x_header, self.state.y_header)

        if self.measure_listener is None:
            raise AppError("Problem with app generation - no associated function for measure display")
        if trajectories:
            self.measure_listener(statespacegrid.measure.get_measures(*trajectories))

    def export_plot(self, path):
        if self.state.matpltlib_fig is None:
            raise AppError("Problem with app generation - no associated grid to save")
        self.state.matpltlib_fig.savefig(fname=path)

    def export_measures(self, path, do_for_individual_trajectories=False):
        trajectories = self.getTrajectories()
        trajectory_ids = self.state.getIDs()
        measures_list = []
        if do_for_individual_trajectories:
            for id, traj in zip(trajectory_ids, trajectories):
                measures_list.append({"id": id} | asdict(statespacegrid.measure.get_measures(traj)))
        else:
            measures_list.append(asdict(statespacegrid.measure.get_measures(*trajectories)))

        with open(path, "w") as ofile:
            pd.DataFrame(measures_list).to_csv(path, index=False)


    def reset(self):
        for reset_func in self.resets:
            reset_func()
        self.state.reset()

    def addDataListener(self, listener):
        self.state.addDataListener(listener)

    def set_plot_structures(self, fig: figure.Figure, ax: axes.Axes):
        self.state.set_plot_structures(fig, ax)

    def getTrajectories(self) -> List[statespacegrid.trajectory.Trajectory]:
        if self.state.x_header is None or self.state.y_header is None or self.state.t_header is None:
            raise AppError("Select a value for the x header, y header and time header before plotting")
        if not self.state.x_range or not self.state.y_range:
            raise AppError("Set the x and y range as a comma separated list in the for '1,2,3' or 'a,b,c' before plotting")

        return [
            statespacegrid.trajectory.Trajectory(
                x_range = self.state.x_range,
                y_range = self.state.y_range,
                states=list(zip(data.data[self.state.x_header].dropna().tolist(), data.data[self.state.y_header].dropna().tolist())),
                times=data.data[self.state.t_header].dropna().astype(float).tolist()
            )
            for data in self.state.getDataObjects()
            if data.selected
        ]

    def read_file(self, file_path):
        extension = os.path.splitext(file_path)[-1]
        if extension in self.file_readers:
            self.file_readers[extension](file_path)
        else:
            raise AppError(f"StateSpaceGridApp can't handle file of extension type {extension}. Please use one of {', '.join(self.file_readers.keys())}")

    @file_reader(".csv")
    def read_csv(self, file_path):
        data = pd.read_csv(file_path, dtype=str)
        self.state.addDataObject(file_path, data)

    @file_reader(".traj")
    def read_traj(self, file_path):
        data = pd.read_csv(file_path, dtype=str, sep="\t")
        self.state.addDataObject(file_path, data)

    @file_reader(".tsv")
    def read_tsv(self, file_path):
        data = pd.read_csv(file_path, dtype=str, sep="\t")
        self.state.addDataObject(file_path, data)

    @file_reader('xls')
    def read_xls(self, file_path):
        data = pd.read_excel(file_path, dtype=str)
        self.state.addDataObject(file_path, data)

    def canHandle(self, extension):
        return extension in self.file_readers


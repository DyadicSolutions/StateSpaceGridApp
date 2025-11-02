import os
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from operator import attrgetter

from pandas import DataFrame
from matplotlib import figure, axes

@dataclass
class DataObjectIdentifier:
    filename: str
    id: Optional[str] = None

    def __str__(self):
        if self.id is not None:
            return f"{self.filename}::{self.id}"
        return self.filename

@dataclass
class DataObjectHolder:
    """
    dataclass to hold a single input file's data
    """
    filename: DataObjectIdentifier
    headers: List[str]
    data: DataFrame
    selected: bool = True

    def splitById(self, id_header):
        return self.data.groupby(id_header)

    def setSelected(self, is_selected):
        self.selected = is_selected

@dataclass
class AppState:
    """
    dataclass to hold all app state data
    """
    data_objects: List[DataObjectHolder] = field(default_factory=list)
    split_data_objects: List[DataObjectHolder] = field(default_factory=list)
    split_by_id: Optional[str] = None
    y_header: Optional[str] = None
    x_header: Optional[str] = None
    t_header: Optional[str] = None
    x_range: List[str] = field(default_factory=list)
    y_range: List[str] = field(default_factory=list)
    matpltlib_fig: Optional[figure.Figure] = None
    matpltlib_ax: Optional[axes.Axes] = None


    data_object_listeners: List[Callable[..., None]] = field(default_factory=list)

    def getDataObjects(self) -> List[DataObjectHolder]:
        return self.split_data_objects if self.split_data_objects else self.data_objects

    def getIDs(self) -> List[str]:
        return [str(data_obj.filename) for data_obj in self.getDataObjects()]

    def update(self):
        """
        For all callbacks in data_object_listeners, pass in a list of DataObjectHolders sorted by filename and id
        """
        data_objects = sorted(self.getDataObjects(), key=attrgetter("filename.filename", "filename.id"))
        for listener in self.data_object_listeners:
            listener(data_objects)

    def addDataObject(self, file_path: str, data: DataFrame):
        headers = list(data.keys())
        filename = os.path.basename(file_path)
        self.data_objects.append(DataObjectHolder(DataObjectIdentifier(filename), headers, data))
        if self.split_by_id:
            self._splitByID(self.data_objects[-1])
        self.update()

    def addDataListener(self, listener: Callable[..., None]):
        self.data_object_listeners.append(listener)

    def _splitByID(self, data_object: DataObjectHolder):
        split_data = list(data_object.data.groupby(self.split_by_id))
        for id, datum in split_data:
            self.split_data_objects.append(
                DataObjectHolder(
                    DataObjectIdentifier(data_object.filename.filename, id=f"{id}"),
                    data_object.headers,
                    datum))

    def addSplitByID(self, id: str):
        self.split_data_objects.clear()
        if id == "":
            self.split_by_id = None
        else:
            self.split_by_id = id
            for data in self.data_objects:
                self._splitByID(data)
        self.update()

    def reset(self):
        self.data_objects.clear()
        self.split_data_objects.clear()
        self.split_by_id = None
        self.x_header = None
        self.y_header = None
        self.t_header = None
        self.update()

    def set_x_header(self, header):
        self.x_header = header

    def set_y_header(self, header):
        self.y_header = header

    def set_t_header(self, header):
        self.t_header = header

    def set_x_range(self, range_list: str):
        self.x_range = [tick.strip() for tick in range_list.split(",")]

    def set_y_range(self, range_list: str):
        self.y_range = [tick.strip() for tick in range_list.split(",")]

    def set_plot_structures(self, fig: figure.Figure, ax: axes.Axes):
        self.matpltlib_fig = fig
        self.matpltlib_ax = ax






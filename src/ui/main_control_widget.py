"""Project-level controls for classifiers."""

# TODO:
# While this file was initially designed for controlling project settings
# This is now the primary location where project-level settings are managed
# The project class simply exposes its settings here which are modified
# The project class should be the management location of these features

import sys

from typing import List
from PySide6 import QtWidgets, QtCore

from src.classifier import Classifier

from .colors import BEHAVIOR_COLOR, NOT_BEHAVIOR_COLOR
from .identity_combo_box import IdentityComboBox
from .k_fold_slider_widget import KFoldSliderWidget
from .label_count_widget import FrameLabelCountWidget


class MainControlWidget(QtWidgets.QWidget):

    label_behavior_clicked = QtCore.Signal()
    label_not_behavior_clicked = QtCore.Signal()
    clear_label_clicked = QtCore.Signal()
    start_selection = QtCore.Signal(bool)
    identity_changed = QtCore.Signal()
    train_clicked = QtCore.Signal()
    classify_clicked = QtCore.Signal()
    classifier_changed = QtCore.Signal()
    behavior_changed = QtCore.Signal(str)
    kfold_changed = QtCore.Signal()
    behavior_list_changed = QtCore.Signal(dict)
    window_size_changed = QtCore.Signal(int)
    new_window_sizes = QtCore.Signal(list)
    use_social_feature_changed = QtCore.Signal(int)
    use_balace_labels_changed = QtCore.Signal(int)
    use_symmetric_changed = QtCore.Signal(int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # initial behavior labels to list in the drop down selection
        self._behaviors = {}

        # behavior selection form components
        self.behavior_selection = QtWidgets.QComboBox()
        self.behavior_selection.addItems(self._behaviors)
        self.behavior_selection.currentIndexChanged.connect(
            self._behavior_changed)

        self.identity_selection = IdentityComboBox()
        self.identity_selection.currentIndexChanged.connect(
            self.identity_changed)
        self.identity_selection.setEditable(False)
        self.identity_selection.installEventFilter(self.identity_selection)

        add_label_button = QtWidgets.QToolButton()
        add_label_button.setText("+")
        add_label_button.setToolTip("Add a new behavior label")
        add_label_button.clicked.connect(self._new_label)

        behavior_layout = QtWidgets.QHBoxLayout()
        behavior_layout.addWidget(self.behavior_selection)
        behavior_layout.addWidget(add_label_button)
        behavior_layout.setContentsMargins(5, 5, 5, 5)

        behavior_group = QtWidgets.QGroupBox("Behavior")
        behavior_group.setLayout(behavior_layout)

        # identity selection form components

        identity_layout = QtWidgets.QVBoxLayout()
        identity_layout.addWidget(self.identity_selection)
        identity_layout.setContentsMargins(5, 5, 5, 5)
        identity_group = QtWidgets.QGroupBox("Subject Identity")
        identity_group.setLayout(identity_layout)

        # classifier menu items (containing getters/setters)
        self._pixel_features_enabled = False
        self._use_pixel_features = {}
        self._social_features_enabled = False
        self._use_social_features = {}
        self._use_window_features = {}
        self._use_fft_features = {}
        self._segmentation_features_enabled = False
        self._use_segmentation_features = {}
        self._use_static_object_features = {}

        # classifier controls
        #  buttons
        self._train_button = QtWidgets.QPushButton("Train")
        self._train_button.clicked.connect(self.train_clicked)
        self._train_button.setEnabled(False)
        self._classify_button = QtWidgets.QPushButton("Classify")
        self._classify_button.clicked.connect(self.classify_clicked)
        self._classify_button.setEnabled(False)

        # drop down to select which window size to use
        self._window_size = QtWidgets.QComboBox()
        self._window_size.currentIndexChanged.connect(
            self._window_size_changed
        )
        self._window_size.setToolTip(
            "Number of frames before and after current frame to include in "
            "sliding window used to compute window features.\n"
            "The total number of frames included in the sliding window is two "
            "times the value of this parameter plus one."
        )

        add_window_size_button = QtWidgets.QToolButton()
        add_window_size_button.setText("+")
        add_window_size_button.setToolTip("Add a new window size")
        add_window_size_button.clicked.connect(self._new_window_size)

        window_size_layout = QtWidgets.QHBoxLayout()
        window_size_layout.addWidget(self._window_size)
        window_size_layout.addWidget(add_window_size_button)

        #  drop down to select type of classifier to use
        self._classifier_selection = QtWidgets.QComboBox()
        self._classifier_selection.currentIndexChanged.connect(
            self.classifier_changed)

        classifier_types = Classifier().classifier_choices()
        for classifier, name in classifier_types.items():
            self._classifier_selection.addItem(name, userData=classifier)

        #  slider to set number of times to train/test
        self._kslider = KFoldSliderWidget()
        self._kslider.valueChanged.connect(self.kfold_changed)
        #   disabled until project loaded
        self._kslider.setEnabled(False)

        self._use_balace_labels_checkbox = QtWidgets.QCheckBox("Balance Training Labels")
        self._use_balace_labels_checkbox.stateChanged.connect(self.use_balace_labels_changed)

        self._symmetric_behavior_checkbox = QtWidgets.QCheckBox("Symmetric Behavior")
        self._symmetric_behavior_checkbox.stateChanged.connect(self.use_symmetric_changed)

        self._all_kfold_checkbox = QtWidgets.QCheckBox("All k-fold Cross Validation")

        #  classifier control layout
        classifier_layout = QtWidgets.QGridLayout()
        classifier_layout.addWidget(self._train_button, 0, 0)
        classifier_layout.addWidget(self._classify_button, 0, 1)
        classifier_layout.addWidget(self._classifier_selection, 1, 0, 1, 2)
        classifier_layout.addWidget(QtWidgets.QLabel("Window Size"), 2, 0)
        classifier_layout.addLayout(window_size_layout, 2, 1)
        classifier_layout.addWidget(self._use_balace_labels_checkbox, 4, 0, 1, 2)
        classifier_layout.addWidget(self._symmetric_behavior_checkbox, 5, 0, 1, 2)
        classifier_layout.addWidget(self._all_kfold_checkbox, 6, 0, 1, 2)
        classifier_layout.addWidget(self._kslider, 7, 0, 1, 2)
        classifier_layout.setContentsMargins(8, 5, 5, 5)
        classifier_group = QtWidgets.QGroupBox("Classifier")
        classifier_group.setLayout(classifier_layout)

        # label components
        label_layout = QtWidgets.QGridLayout()

        self._label_behavior_button = QtWidgets.QPushButton()
        self._label_behavior_button.clicked.connect(self.label_behavior_clicked)
        self._label_behavior_button.setStyleSheet(f"""
                    QPushButton {{
                        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                           stop: 0 rgb(255, 195, 77),
                                           stop: 1.0 rgb{BEHAVIOR_COLOR});
                        border-radius: 4px;
                        padding: 2px;
                        color: white;
                    }}
                    QPushButton:pressed {{
                        background-color: rgb(255, 195, 77);
                    }}
                    QPushButton:disabled {{
                        background-color: rgb(229, 143, 0);
                        color: grey;
                    }}
                """)

        self._label_not_behavior_button = QtWidgets.QPushButton()
        self._label_not_behavior_button.clicked.connect(
            self.label_not_behavior_clicked)
        self._label_not_behavior_button.setStyleSheet(f"""
                    QPushButton {{
                        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                           stop: 0 rgb(50, 119, 234),
                                           stop: 1.0 rgb{NOT_BEHAVIOR_COLOR});
                        border-radius: 4px;
                        padding: 2px;
                        color: white;
                    }}
                    QPushButton:pressed {{
                        background-color: rgb(50, 119, 234);
                    }}
                    QPushButton:disabled {{
                        background-color: rgb(0, 77, 206);
                        color: grey;
                    }}
                """)

        self._clear_label_button = QtWidgets.QPushButton("Clear Label")
        self._clear_label_button.clicked.connect(self.clear_label_clicked)

        self._select_button = QtWidgets.QPushButton("Select Frames")
        self._select_button.setCheckable(True)
        self._select_button.clicked.connect(self.start_selection)
        # disabled until a project is loaded
        self._select_button.setEnabled(False)

        # label buttons are disabled unless user has a range of frames selected
        self.disable_label_buttons()

        label_layout.addWidget(self._label_behavior_button, 0, 0, 1, 2)
        label_layout.addWidget(self._label_not_behavior_button, 1, 0, 1, 2)
        label_layout.addWidget(self._clear_label_button, 2, 0)
        label_layout.addWidget(self._select_button, 2, 1)
        label_layout.setContentsMargins(5, 5, 5, 5)
        label_group = QtWidgets.QGroupBox("Labeling")
        label_group.setLayout(label_layout)

        # summary of number of frames / bouts for each class
        self._frame_counts = FrameLabelCountWidget()
        label_count_layout = QtWidgets.QVBoxLayout()
        label_count_layout.addWidget(self._frame_counts)
        label_count_group = QtWidgets.QGroupBox("Label Summary")
        label_count_group.setLayout(label_count_layout)

        # control layout
        control_layout = QtWidgets.QVBoxLayout()
        if sys.platform == 'darwin':
            control_layout.setSpacing(20)
        else:
            control_layout.setSpacing(10)
        control_layout.addWidget(behavior_group)
        control_layout.addWidget(identity_group)
        control_layout.addWidget(classifier_group)
        control_layout.addWidget(label_count_group)
        control_layout.addStretch()
        control_layout.addWidget(label_group)

        self.setLayout(control_layout)

    @property
    def current_behavior(self):
        return self.behavior_selection.currentText()

    @property
    def behaviors(self):
        """ return a copy of the current list of behaviors """
        return dict(self._behaviors)

    @property
    def current_identity(self):
        return self.identity_selection.currentText()

    @property
    def current_identity_index(self):
        return self.identity_selection.currentIndex()

    @property
    def select_button_is_checked(self):
        return self._select_button.isChecked()

    @property
    def kfold_value(self):
        return self._kslider.value()

    @property
    def train_button_enabled(self):
        return self._train_button.isEnabled()

    @property
    def classify_button_enabled(self):
        return self._classify_button.isEnabled()

    @train_button_enabled.setter
    def train_button_enabled(self, enabled: bool):
        self._train_button.setEnabled(enabled)

    @property
    def classifier_type(self):
        return self._classifier_selection.currentData()

    @property
    def use_pixel_features(self):
        return self._use_pixel_features.get(self.current_behavior, self._pixel_features_enabled)

    @use_pixel_features.setter
    def use_pixel_features(self, val: bool):
        if self._pixel_features_enabled:
            self._use_pixel_features[self.current_behavior] = val

    @property
    def use_social_features(self):
        return self._use_social_features.get(self.current_behavior, self._social_features_enabled)

    @use_social_features.setter
    def use_social_features(self, val: bool):
        if self._social_features_enabled:
            self._use_social_features[self.current_behavior] = val

    @property
    def use_window_features(self):
        return self._use_window_features.get(self.current_behavior, True)

    @use_window_features.setter
    def use_window_features(self, val: bool):
        self._use_window_features[self.current_behavior] = val

    @property
    def use_fft_features(self):
        return self._use_fft_features.get(self.current_behavior, True)

    @use_fft_features.setter
    def use_fft_features(self, val: bool):
        self._use_fft_features[self.current_behavior] = val

    @property
    def use_segmentation_features(self):
        return self._use_segmentation_features.get(self.current_behavior, self._segmentation_features_enabled)

    @use_segmentation_features.setter
    def use_segmentation_features(self, val: bool):
        if self._segmentation_features_enabled:
            self._use_segmentation_features[self.current_behavior] = val

    def enable_static_objects(self, object_list):
        """ adds objects to be toggle-able. """
        for obj in object_list:
            self._use_static_object_features[obj] = {}

    def toggle_static_object_features(self, val: bool, obj: str):
        """ toggles using a static object feature. """
        if obj in self._use_static_object_features:
            self._use_static_object_features[obj][self.current_behavior] = val

    def get_static_object_features(self, obj: str):
        """ gets the state of static object features. """
        if obj in self._use_static_object_features:
            self._use_static_object_features[obj].get(self.current_behavior, True)
        else:
            return False

    @property
    def use_balance_labels(self):
        return self._use_balace_labels_checkbox.isChecked()

    @use_balance_labels.setter
    def use_balance_labels(self, val: bool):
        if self._use_balace_labels_checkbox.isEnabled():
            self._use_balace_labels_checkbox.setChecked(val)

    @property
    def use_symmetric(self):
        return self._symmetric_behavior_checkbox.isChecked()

    @use_symmetric.setter
    def use_symmetric(self, val: bool):
        if self._symmetric_behavior_checkbox.isEnabled():
            self._symmetric_behavior_checkbox.setChecked(val)

    @property
    def all_kfold(self):
        return self._all_kfold_checkbox.isChecked()

    def disable_label_buttons(self):
        """ disable labeling buttons that require a selected range of frames """
        self._label_behavior_button.setEnabled(False)
        self._label_not_behavior_button.setEnabled(False)
        self._clear_label_button.setEnabled(False)
        self._select_button.setChecked(False)

    def enable_label_buttons(self):
        self._label_behavior_button.setEnabled(True)
        self._label_not_behavior_button.setEnabled(True)
        self._clear_label_button.setEnabled(True)

    def set_use_balance_labels_checkbox_enabled(self, val: bool):
        self._use_balace_labels_checkbox.setEnabled(val)
        if not val:
            self._use_balace_labels_checkbox.setChecked(False)

    def set_use_symmetric_checkbox_enabled(self, val: bool):
        self._use_symmetric_checkbox.setEnabled(val)
        if not val:
            self._use_symmetric_checkbox.setChecked(False)

    def set_classifier_selection(self, classifier_type):
        try:
            index = self._classifier_selection.findData(classifier_type)
            if index != -1:
                self._classifier_selection.setCurrentIndex(index)
        except KeyError:
            # unable to use the classifier
            pass

    def set_frame_counts(self, label_behavior_current,
                         label_not_behavior_current,
                         label_behavior_project,
                         label_not_behavior_project,
                         bout_behavior_current,
                         bout_not_behavior_current,
                         bout_behavior_project,
                         bout_not_behavior_project):
        self._frame_counts.set_counts(label_behavior_current,
                                      label_not_behavior_current,
                                      label_behavior_project,
                                      label_not_behavior_project,
                                      bout_behavior_current,
                                      bout_not_behavior_current,
                                      bout_behavior_project,
                                      bout_not_behavior_project)

    def classify_button_set_enabled(self, enabled: bool):
        self._classify_button.setEnabled(enabled)

    def select_button_set_enabled(self, enabled: bool):
        self._select_button.setEnabled(enabled)

    def select_button_set_checked(self, checked):
        self._select_button.setChecked(checked)

    def toggle_select_button(self):
        self._select_button.toggle()

    def kslider_set_enabled(self, enabled: bool):
        self._kslider.setEnabled(enabled)

    def set_identity_index(self, i: int):
        self.identity_selection.setCurrentIndex(i)

    def update_project_settings(self, project_settings: dict):
        """
        update controls from project settings
        :param project_settings: dict containing project settings
        :return: None
        """

        # TODO: This is one of the major locations where project settings
        # are owned by this widget, instead of the project class

        # update window sizes
        self._set_window_sizes(project_settings['window_sizes'])

        # update behaviors
        # reset list of behaviors, then add any from the project metadata
        self._behaviors = {}

        # we don't need this even handler to be active while we set up the
        # project (otherwise it gets unnecessarily called multiple times)
        self.behavior_selection.currentIndexChanged.disconnect()

        behavior_index = 0
        if 'behaviors' in project_settings:
            self._behaviors = project_settings['behaviors']
        self.behavior_selection.clear()
        self.behavior_selection.addItems(self._behaviors.keys())
        if 'selected_behavior' in project_settings:
            # make sure this behavior is in the behavior selection drop down
            if project_settings['selected_behavior'] not in self._behaviors:
                self._behaviors[project_settings['selected_behavior']] = project_settings['defaults']
                self.behavior_selection.clear()
                self.behavior_selection.addItems(self._behaviors.keys())
            behavior_index = list(self._behaviors.keys()).index(
                project_settings['selected_behavior'])

        # set the index to either the first behavior, or if available, the one
        # that was saved in the project metadata
        self.behavior_selection.setCurrentIndex(behavior_index)
        if len(self._behaviors) == 0:
            self._get_first_label()
        else:
            self._label_behavior_button.setText(self.current_behavior)
            self._label_behavior_button.setToolTip(
                f"Label frames {self.current_behavior}")
            self._label_not_behavior_button.setText(
                f"Not {self.current_behavior}")
            self._label_not_behavior_button.setToolTip(
                f"Label frames Not {self.current_behavior}")

        # use window size last used for the behavior
        window_settings = project_settings.get('window_size_pref', {})
        if self.current_behavior in window_settings:
            self.set_window_size(window_settings[self.current_behavior])

        # set initial state for use social feature button
        optional_feature_settings = project_settings.get(
            'optional_features', {})
        social_feature_settings = optional_feature_settings.get('social', {})
        if self.current_behavior in social_feature_settings:
            self.use_social_features = social_feature_settings[self.current_behavior]

        balance_labels_settings = optional_feature_settings.get('balance', {})
        if self.current_behavior in balance_labels_settings:
            self.use_balance_labels = balance_labels_settings[self.current_behavior]

        symmetric_settings = optional_feature_settings.get('symmetric', {})
        if self.current_behavior in symmetric_settings:
            self.use_symmetric = symmetric_settings[self.current_behavior]

        # re-enable the behavior_selection change signal handler
        self.behavior_selection.currentIndexChanged.connect(
            self._behavior_changed)

    def set_identities(self, identities):
        """ populate the identity_selection combobox """
        self.identity_selection.currentIndexChanged.disconnect()
        self.identity_selection.clear()
        self.identity_selection.currentIndexChanged.connect(
            self.identity_changed)
        self.identity_selection.addItems([str(i) for i in identities])

    def set_window_size(self, size: int):
        """ set the current window size """
        if self._window_size.findData(size) == -1:
            self._add_window_size(size)
        self._window_size.setCurrentText(str(size))

    def remove_behavior(self, behavior: str):
        idx = self.behavior_selection.findText(behavior, QtCore.Qt.MatchExactly)
        if idx != -1:
            self.behavior_selection.removeItem(idx)
            self._behaviors.remove(behavior)
        self.behavior_list_changed.emit(self._behaviors)

    def _set_window_sizes(self, sizes: List[int]):
        """ set the list of available window sizes """
        self._window_size.clear()
        for w in sizes:
            self._window_size.addItem(str(w), userData=w)

    def _new_label(self):
        """
        callback for the "new behavior" button
        opens a modal dialog to allow the user to enter a new behavior label,
        if user clicks ok, add that behavior to the combo box, and select it
        """
        text, ok = QtWidgets.QInputDialog.getText(self, 'New Behavior',
                                                  'New Behavior Name:',
                                                  QtWidgets.QLineEdit.Normal
                                                  )
        if ok and text not in self._behaviors:
            self._behaviors[text] = {}
            self.behavior_selection.addItem(text)
            self.behavior_selection.setCurrentText(text)
            self.behavior_list_changed.emit(self._behaviors)

    def _get_first_label(self):
        """
        show the new label dialog until the user enters one. Used when
        opening a new project for the fist time.
        TODO: make custom dialog so the user can't close the dialog until
          they've entered a behavior label
        """
        ok = False
        text = ""

        while not ok:
            text, ok = QtWidgets.QInputDialog.getText(
                self, 'New Behavior',
                'New project - please enter a behavior name to continue:',
                QtWidgets.QLineEdit.Normal)
        self._behaviors[text] = {}
        self.behavior_selection.addItem(text)
        self.behavior_selection.setCurrentText(text)
        self.behavior_list_changed.emit(self._behaviors)
        self._behavior_changed()

    def _new_window_size(self):
        """
        callback for the "new window size" button
        opens a modal dialog to allow the user to enter a new window size,
        if user clicks ok, add that window size and select it
        """
        val, ok = QtWidgets.QInputDialog.getInt(
            self, 'New Window Size', 'Enter a new window size:', value=1,
            minValue=1)
        if ok:
            # if this window size is not already in the drop down, add it.
            if self._window_size.findData(val) == -1:
                self._add_window_size(val)

            # select new window size
            self.set_window_size(val)
            QtWidgets.QMessageBox.warning(
                self, "Window Size Added",
                "Window Size Added.\n"
                "If features have not been computed for "
                "this window size, they will be computed the first time a "
                "classifier is trained using this window size.\n"
                "This may be slow.")

    def _add_window_size(self, new_size: int):
        # we clear and reset the contents of the combo box so that we
        # can re sort it with the new size

        # grab the old sizes, grabbing the data (int) instead of the
        # text
        sizes = [self._window_size.itemData(i) for i in
                 range(self._window_size.count())]

        # add our new value and sort
        sizes.append(new_size)
        sizes.sort()

        # clear and add in the new list of sizes
        self._window_size.clear()
        for s in sizes:
            self._window_size.addItem(str(s), userData=s)

        # send a signal that we have an updated list of window sizes
        self.new_window_sizes.emit(sizes)

    def _behavior_changed(self):
        self._label_behavior_button.setText(self.current_behavior)
        self._label_behavior_button.setToolTip(
            f"Label frames {self.current_behavior}")
        self._label_not_behavior_button.setText(
            f"Not {self.current_behavior}")
        self._label_not_behavior_button.setToolTip(
            f"Label frames Not {self.current_behavior}")
        self.behavior_changed.emit(self.current_behavior)

    def _window_size_changed(self):
        self.window_size_changed.emit(self._window_size.currentData())

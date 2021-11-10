import typing

import numpy as np
import scipy.stats

from src.feature_extraction.feature_base_class import Feature

if typing.TYPE_CHECKING:
    from .social_distance import ClosestIdentityInfo
    from src.pose_estimation import PoseEstimation


class ClosestFovAngles(Feature):

    _name = 'closest_fov_angles'

    # override for circular values
    _window_operations_circular_2 = {
        "mean": lambda x: scipy.stats.circmean(x, low=-180, high=180),
        "std_dev": lambda x: scipy.stats.circstd(x, low=-180, high=180),
    }

    def __init__(self, poses: 'PoseEstimation', pixel_scale: float,
                 social_distance_info: 'ClosestIdentityInfo'):
        super().__init__(poses, pixel_scale)
        self._social_distance_info = social_distance_info

    @property
    def feature_names(self) -> typing.List[str]:
        return ['angle of closest social distance in FoV']

    def per_frame(self, identity: int) -> np.ndarray:
        # this is already computed
        return self._social_distance_info.closest_fov_angles

    def window(self, identity: int, window_size: int,
               per_frame_values: np.ndarray) -> typing.Dict:
        # need to override to use special method for computing window features
        # with circular values
        return self._window_circular(identity, window_size, per_frame_values)

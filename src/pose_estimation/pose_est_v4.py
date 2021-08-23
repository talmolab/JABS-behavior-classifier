import typing
from pathlib import Path

import h5py
import numpy as np

from .pose_est import PoseEstimation


class PoseEstimationV4(PoseEstimation):
    """
    class for opening and parsing version 4 of the pose estimation HDF5 file
    """

    __CACHE_FILE_VERSION = 1

    def __init__(self, file_path: Path, cache_dir: typing.Optional[Path]=None):
        """
        :param file_path: Path object representing the location of the pose file
        """
        super().__init__(file_path, cache_dir)

        self._identity_to_track = None
        self._identity_map = None

        # open the hdf5 pose file
        with h5py.File(self._path, 'r') as pose_h5:
            # extract data from the HDF5 file
            pose_grp = pose_h5['poseest']
            major_version = pose_grp.attrs['version'][0]

            # get pixel size
            self._cm_per_pixel = pose_grp.attrs.get('cm_per_pixel')

            # ensure the major version matches what we expect
            # TODO temporarily removed while v4 files under development
            #assert major_version == 4

            # load contents
            all_points = pose_grp['points'][:]
            all_confidence = pose_grp['confidence'][:]
            id_mask = pose_grp['id_mask'][:]
            instance_embed_id = pose_grp['instance_embed_id'][:]

        self._num_frames = len(all_points)
        self._num_identities = np.max(np.ma.array(instance_embed_id[...], mask=id_mask[...]))

        # generate list of identities based on the max number of instances in
        # the pose file
        self._identities = [*range(self._num_identities)]

        points_by_id_tmp = np.zeros_like(all_points)
        points_by_id_tmp[np.where(id_mask == 0)[0], instance_embed_id[id_mask == 0] - 1, :, :] = all_points[id_mask == 0, :, :]
        self._points = np.transpose(points_by_id_tmp, [1, 0, 2, 3])

        confidence_by_id_tmp = np.zeros_like(all_confidence)
        confidence_by_id_tmp[np.where(id_mask == 0)[0], instance_embed_id[id_mask == 0] - 1, :] = all_confidence[id_mask == 0, :]
        confidence_by_id = np.transpose(confidence_by_id_tmp, [1, 0, 2])

        self._point_mask = confidence_by_id > 0

        # build a mask for each identity that indicates if it exists or not
        # in the frame
        init_func = np.vectorize(
            lambda x, y: 0 if np.sum(self._point_mask[x][y][:-2]) == 0 else 1,
            otypes=[np.uint8])
        self._identity_mask = np.fromfunction(
            init_func, (self._num_identities, self._num_frames), dtype=np.int_)

    @property
    def identity_to_track(self):
        return None

    @property
    def format_major_version(self):
        return 4

    def get_points(self, frame_index, identity):
        """
        get points and mask for an identity for a given frame
        :param frame_index: index of frame
        :param identity: identity that we want the points for
        :return: points, mask if identity has data for this frame
        """

        if not self._identity_mask[identity, frame_index]:
            return None, None

        return (
            self._points[identity, frame_index, ...],
            self._point_mask[identity, frame_index, :]
        )

    def get_identity_poses(self, identity):
        return self._points[identity, ...], self._point_mask[identity, ...]

    def identity_mask(self, identity):
        return self._identity_mask[identity,:]

    def get_identity_point_mask(self, identity):
        """
        get the point mask array for a given identity
        :param identity: identity to return point mask for
        :return: array of point masks (#frames, 12)
        """
        return self._point_mask[identity, :]

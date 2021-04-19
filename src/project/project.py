import gzip
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np

import src.feature_extraction as fe
from src.pose_estimation import get_pose_path, open_pose_file, \
    get_frames_from_file
from src.project import TrackLabels
from src.version import version_str
from src.video_stream import VideoStream
from src.video_stream.utilities import get_frame_count, get_fps
from .video_labels import VideoLabels


class Project:
    """ represents a labeling project """

    # subdirectory app creates inside project directory to store app-specific
    # project data
    _PROJ_DIR = 'rotta'
    __PROJECT_SETTING_FILE = 'project_settings.json'
    __PROJECT_FILE = 'project.json'
    __DEFAULT_UMASK = 0o775

    PREDICTION_FILE_VERSION = 1

    def __init__(self, project_path, use_cache=True, enable_video_check=True):
        """
        Open a project at a given path. A project is a directory that contains
        avi files and their corresponding pose_est_v3.h5 files as well as json
        files containing project metadata and annotations.
        :param project_path: path to project directory

        TODO: catch ValueError that this might raise when opening a project
        """

        # make sure this is a pathlib.Path and not a string
        self._project_dir_path = Path(project_path)
        self._annotations_dir = (self._project_dir_path / self._PROJ_DIR /
                                 "annotations")
        self._feature_dir = (self._project_dir_path / self._PROJ_DIR /
                             "features")
        self._prediction_dir = (self._project_dir_path / self._PROJ_DIR /
                                "predictions")
        self._project_file = (self._project_dir_path / self._PROJ_DIR /
                              self.__PROJECT_FILE)
        self._classifier_dir = (self._project_dir_path / self._PROJ_DIR /
                                'classifiers')
        self._archive_dir = (self._project_dir_path / self._PROJ_DIR /
                             'archive')

        if use_cache:
            self._cache_dir = (self._project_dir_path / self._PROJ_DIR /
                               'cache')
        else:
            self._cache_dir = None

        # if project directory doesn't exist, create it (empty project)
        # parent directory must exist.
        Path(project_path).mkdir(mode=self.__DEFAULT_UMASK, exist_ok=True)

        # make sure the app subdirectory directory exists to store project
        # metadata and annotations
        Path(project_path, self._PROJ_DIR).mkdir(mode=self.__DEFAULT_UMASK,
                                                 exist_ok=True)

        # make sure other app directories exist
        self._annotations_dir.mkdir(mode=self.__DEFAULT_UMASK, exist_ok=True)
        self._feature_dir.mkdir(mode=self.__DEFAULT_UMASK, exist_ok=True)
        self._prediction_dir.mkdir(mode=self.__DEFAULT_UMASK, exist_ok=True)
        self._archive_dir.mkdir(mode=self.__DEFAULT_UMASK, exist_ok=True)

        if use_cache:
            self._cache_dir.mkdir(mode=self.__DEFAULT_UMASK, exist_ok=True)

        # load any saved project metadata
        self._metadata = self.load_metadata()

        self._total_project_identities = 0

        # get list of video files in the project directory
        self._videos = self.get_videos(self._project_dir_path)
        self._videos.sort()

        err = False
        for v in self.videos:
            if self.__has_pose(v) is False:
                print(f"{v} missing pose file", file=sys.stderr)
                err = True
        if err:
            raise ValueError("Project missing pose file for one or more video")

        if enable_video_check:
            err = False
            for v in self.videos:
                path = get_pose_path(self.video_path(v))
                pose_frames = get_frames_from_file(path)
                vid_frames = VideoStream.get_nframes_from_file(self.video_path(v))
                if pose_frames != vid_frames:
                    print(f"{v}: video and pose file have different number of frames",
                          file=sys.stderr)
                    err = True
            if err:
                raise ValueError("Video and Pose File frame counts differ")

        video_metadata = self._metadata.get('video_files', {})
        for video in self._videos:
            vinfo = {}
            if video in video_metadata:
                nidentities = video_metadata[video].get('identities')
                pose_hash = video_metadata[video].get('pose_hash')
                vid_hash = video_metadata[video].get('vid_hash')
                vinfo = video_metadata[video]
            else:
                nidentities = None
                pose_hash = None
                vid_hash = None

            # if the number of identities is not cached in the project metadata,
            # open the pose file to get it
            if nidentities is None:
                # this will raise a ValueError if the video does not have a
                # corresponding pose file.
                pose_file = open_pose_file(
                    get_pose_path(self.video_path(video)), self._cache_dir)
                nidentities = pose_file.num_identities
                vinfo['identities'] = nidentities
            if pose_hash is None:
                vinfo['pose_hash'] = self.__hash_file(
                    get_pose_path(self.video_path(video)))
            if vid_hash is None:
                vinfo['vid_hash'] = self.__hash_file(self.video_path(video))

            self._total_project_identities += nidentities
            video_metadata[video] = vinfo
        self.save_metadata({'video_files': video_metadata})

        # determine if this project relies on social features or not
        self._has_social_features = False
        for i, vid in enumerate(self._videos):
            vid_path = self.video_path(vid)
            pose_path = get_pose_path(vid_path)
            curr_has_social = pose_path.name.endswith('v3.h5')

            if i == 0:
                self._has_social_features = curr_has_social
            else:
                # here we're just making sure everything is consistent,
                # otherwise we throw a ValueError
                if curr_has_social != self._has_social_features:
                    raise ValueError('Found a pose estimation mismatch in project')

    @property
    def videos(self):
        """
        get list of video files that are in this project directory
        :return: list of file names (file names only, without path)
        """
        return self._videos

    @property
    def dir(self) -> Path:
        return self._project_dir_path

    @property
    def feature_dir(self) -> Path:
        return self._feature_dir

    @property
    def annotation_dir(self) -> Path:
        return self._annotations_dir

    @property
    def has_social_features(self):
        return self._has_social_features

    @property
    def metadata(self):
        """
        get the project metadata and preferences.

        Returns a copy of the metadata dict, so that self._info can't be
        modified
        """
        return dict(self._metadata)

    @property
    def classifier_dir(self):
        return self._classifier_dir

    @property
    def total_project_identities(self):
        """
        sum the number of instances across all videos in the project
        :return: integer sum
        """
        return self._total_project_identities

    def load_video_labels(self, video_name):
        """
        load labels for a video from the project directory or from a cached of
        annotations that have previously been opened and not yet saved
        :param video_name: filename of the video: string or pathlib.Path
        :return: initialized VideoLabels object
        """

        video_filename = Path(video_name).name
        self.check_video_name(video_filename)

        path = self._annotations_dir / Path(video_filename).with_suffix('.json')

        # if annotations already exist for this video file in the project open
        # it, otherwise create a new empty VideoLabels
        if path.exists():
            with path.open() as f:
                return VideoLabels.load(json.load(f))
        else:
            video_path = self._project_dir_path / video_filename
            nframes = get_frame_count(str(video_path))
            return VideoLabels(video_filename, nframes)

    @staticmethod
    def to_safe_name(behavior: str):
        """
        Create a version of the given behavior name that
        should be safe to use in filenames.
        :param behavior: string behavior name
        """
        safe_behavior = re.sub('[^0-9a-zA-Z]+', '_', behavior).rstrip('_')
        # get rid of consecutive underscores
        safe_behavior = re.sub('_{2,}', '_', safe_behavior)
        return safe_behavior

    def load_pose_est(self, video_path: Path):
        """
        return a PoseEstimation object for a given video path
        :param video_path: pathlib.Path containing location of video file
        :return: PoseEstimation object (PoseEstimationV2 or PoseEstimationV3)
        :raises ValueError: if video no in project or it does not have post file
        """
        # ensure this video path is for a valid project video
        video_filename = Path(video_path).name
        self.check_video_name(video_filename)

        return open_pose_file(get_pose_path(video_path), self._cache_dir)

    def check_video_name(self, video_filename):
        """
        make sure the video name actually matches one in the project, this
        function will raise a ValueError if the video name is not valid,
        otherwise the function has no effect
        :param video_filename:
        :return: None
        :raises: ValueError if the filename is not a valid video in this project
        """
        if video_filename not in self._videos:
            raise ValueError(f"{video_filename} not in project")

    def save_annotations(self, annotations: VideoLabels):
        """
        save state of a VideoLabels object to the project directory
        :param annotations: VideoLabels object
        :return: None
        """
        path = self._annotations_dir / Path(
            annotations.filename).with_suffix('.json')

        with path.open(mode='w', newline='\n') as f:
            json.dump(annotations.as_dict(), f, indent=2)

        # update app version saved in project metadata if necessary
        self.__update_version()

    def save_metadata(self, data: dict):
        """
        save project settings and metadata into the project directory. This may
        include things like custom behavior labels added by the user as well
        as the most recently selected behavior label

        any keys in the project metadata dict not included in the data, will
        not be modified
        :param data: dictionary with state information to save
        :return: None
        """

        # merge data with current metadata
        self._metadata.update(data)
        self._metadata['version'] = version_str()

        # save combined info to file
        with self._project_file.open(mode='w', newline='\n') as f:
            json.dump(self._metadata, f, indent=2, sort_keys=True)

    def load_metadata(self):
        """
        load project metadata
        :return: dictionary of project metadata, empty dict if unable to open
        file (such as when the prject is first created and the file does not
        exist)
        """
        try:
            with self._project_file.open(mode='r', newline='\n') as f:
                settings = json.load(f)
        except:
            settings = {}

        if 'window_sizes' not in settings:
            settings['window_sizes'] = [fe.DEFAULT_WINDOW_SIZE]

        return settings

    def save_classifier(self, classifier, behavior: str):
        """
        Save the classifier for the given behavior
        :param classifier: the classifier to save
        :param behavior: string behavior name. This affects the path we save to
        """
        self._classifier_dir.mkdir(parents=True, exist_ok=True)
        classifier.cache_classifier(
            self._classifier_dir / (self.to_safe_name(behavior) + '.pickle')
        )

        # update app version saved in project metadata if necessary
        self.__update_version()

    def load_classifier(self, classifier, behavior: str):
        """
        Load cached classifier for the given behavior
        :param classifier: the classifier to load
        :param behavior: string behavior name.
        :return: True if load is successful and False if the file doesn't exist
        """
        classifier_path = (
            self._classifier_dir / (self.to_safe_name(behavior) + '.pickle')
        )
        try:
            classifier.load_cached_classifier(classifier_path)
            return True
        except OSError:
            return False

    def save_predictions(self, predictions, probabilities,
                         frame_indexes, behavior: str):
        """
        save predictions for the current project
        :param predictions: predictions for all videos in project (dictionary
        with each video name as a key and a numpy array (#identities, #frames))
        :param probabilities: corresponding prediction probabilities, similar
        structure to predictions parameter but with floating point values
        :param frame_indexes: mapping of the predictions to video frames
        :param behavior: string behavior name

        Because the classifier does not run on every frame for every identity
        (since an identity may not exist for every frame), we extract just
        the features for the frames we need to classify. Now we want to map
        these back to the corresponding frame.
        predictions[video_name][identity, index] and
        probabilities[video_name][identity, index] correspond to the frame
        specified by frame_indexes[video][identity, index]
        """

        for video in self._videos:
            # setup an ouptut filename based on the behavior and video names
            file_base = Path(video).with_suffix('').name + ".h5"
            output_path = self._prediction_dir / self.to_safe_name(
                behavior) / file_base

            # make sure behavior directory exists
            output_path.parent.mkdir(exist_ok=True)

            # we need some info from the PoseEstimation and VideoLabels objects
            # associated with this video
            video_tracks = self.load_video_labels(video)
            poses = open_pose_file(get_pose_path(self.video_path(video)),
                                   self._cache_dir)

            # allocate numpy arrays to write to h5 file
            prediction_labels = np.full(
                (poses.num_identities, video_tracks.num_frames), -1,
                dtype=np.int8)
            prediction_prob = np.zeros_like(prediction_labels, dtype=np.float32)

            # populate numpy arrays
            for identity in predictions[video]:
                identity_index = int(identity)

                inferred_indexes = frame_indexes[video][identity]
                track = video_tracks.get_track_labels(identity, behavior)
                manual_labels = track.get_labels()

                prediction_labels[identity_index, inferred_indexes] = predictions[video][identity]
                prediction_prob[identity_index, inferred_indexes] = probabilities[video][identity]

                # manual labels are saved with the predictions, but the
                # probability is set to -1 to indicate that the class was
                # manually assigned by the user and not inferred
                prediction_labels[identity_index,
                    manual_labels == track.Label.NOT_BEHAVIOR] = track.Label.NOT_BEHAVIOR.value
                prediction_prob[identity_index, manual_labels == track.Label.NOT_BEHAVIOR] = -1.0
                prediction_labels[identity_index,
                    manual_labels == track.Label.BEHAVIOR] = track.Label.BEHAVIOR.value
                prediction_prob[identity_index, manual_labels == track.Label.BEHAVIOR] = -1.0

            # write to h5 file
            # TODO catch exceptions
            with h5py.File(output_path, 'w') as h5:
                h5.attrs['version'] = self.PREDICTION_FILE_VERSION
                group = h5.create_group('predictions')
                group.create_dataset('predicted_class', data=prediction_labels)
                group.create_dataset('probabilities', data=prediction_prob)
                group.create_dataset('identity_to_track', data=poses.identity_to_track)

        # update app version saved in project metadata if necessary
        self.__update_version()

    def load_predictions(self, video: str, behavior: str):
        """
        load predictions for a given video and behavior
        :param video: name of video to load predictions for
        :param behavior: behavior to load predictions for
        :return: tuple of three dicts: (predictions, probabilities, frame_indexes)
        each dict has identities present in the video for keys
        """

        predictions = {}
        probabilities = {}
        frame_indexes = {}

        file_base = Path(video).with_suffix('').name + ".h5"
        path = self._prediction_dir / self.to_safe_name(behavior) / file_base

        nident = self._metadata['video_files'][video]['identities']

        try:
            with h5py.File(path, 'r') as h5:
                assert h5.attrs['version'] == self.PREDICTION_FILE_VERSION
                group = h5['predictions']
                assert group['predicted_class'].shape[0] == nident
                assert group['probabilities'].shape[0] == nident

                _probabilities = group['probabilities'][:]
                _classes = group['predicted_class'][:]

                for i in range(nident):
                    identity = str(i)
                    indexes = np.asarray(range(group['predicted_class'].shape[1]))

                    # first, exclude any probability of -1 as that indicates
                    # a user label, not a inferred class
                    indexes = indexes[_probabilities[i] != -1]

                    # now excludes a class of -1 as that indicates the
                    # identity isn't present
                    indexes = indexes[_classes[i, indexes] != -1]

                    # we're left with classes/probabilities for frames that
                    # were inferred and their frame indexes
                    predictions[identity] = _classes[i, indexes]
                    probabilities[identity] = _probabilities[i, indexes]
                    frame_indexes[identity] = indexes

        except IOError:
            # no saved predictions for this video
            pass
        except (AssertionError, KeyError) as e:
            print(f"unable to open saved inferences for {video}", file=sys.stderr)

        return predictions, probabilities, frame_indexes

    def archive_behavior(self, behavior: str):
        """
        Archive a behavior.
        Archives any labels for this behavior. Deletes any other files
        associated with this behavior.
        :param behavior: string behavior name
        :return: None
        """

        safe_behavior = self.to_safe_name(behavior)

        # remove predictions
        path = self._prediction_dir / safe_behavior
        shutil.rmtree(path, ignore_errors=True)

        # remove classifier
        path = self._classifier_dir / f"{safe_behavior}.pickle"
        try:
            path.unlink()
        except FileNotFoundError:
            pass

        # archive labels
        archived_labels = {}
        for video in self._videos:
            annotations = self.load_video_labels(video).as_dict()
            for ident in annotations['labels']:
                if behavior in annotations['labels'][ident]:
                    if video not in archived_labels:
                        archived_labels[video] = {
                            'num_frames': annotations['num_frames']
                        }
                        archived_labels[video][behavior] = {}
                    archived_labels[video][behavior][ident] = annotations['labels'][ident].pop(behavior)
            self.save_annotations(VideoLabels.load(annotations))

        # write the archived labels out
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        with gzip.open(self._archive_dir / f"{safe_behavior}_{ts}.json.gz", 'wt') as f:
            json.dump(archived_labels, f, indent=True)

    def video_path(self, video_file):
        """ take a video file name and generate the path used to open it """
        return Path(self._project_dir_path, video_file)

    def counts(self, behavior):
        """
        get the labeled frame counts and bout counts for each video in the
        project
        :return: dict where keys are video names and values are lists of
        (
            identity,
            (behavior frame count, not behavior frame count),
            (behavior bout count, not behavior bout count)
        )
        """
        counts = {}
        for video in self._videos:
            counts[video] = self.__read_counts(video, behavior)
        return counts

    @staticmethod
    def get_videos(dir_path: Path):
        """ Get list of video filenames (without path) in a directory """
        return [f.name for f in dir_path.glob("*.avi")]

    def get_labeled_features(self, behavior, window_size,
                             progress_callable=None):
        """
        the the features for all labeled frames
        NOTE: this will currently take a very long time to run if the features
        have not already been computed

        :param behavior: the behavior to get labeled features for
        :param window_size: window size to use for computing window features
        :param progress_callable: if provided this will be called
        with no args every time an identity is processed to facilitate
        progress tracking

        :return: two dicts: features, group_mappings

        The first dict contains features for all labeled frames and has the
        following keys:

        {
            'window': ,
            'per_frame': ,
            'labels': ,
            'groups': ,
        }

        The values contained in the first dict are suitable to pass as
        arguments to the Classifier.leave_one_group_out() method.

        The second dict in the tuple has group ids as the keys, and the
        values are a dict containing the video and identity that corresponds to
        that group id:

        {
          <group id>: {'video': <video filename>, 'identity': <identity},
          ...
        }
        """

        all_per_frame = []
        all_window = []
        all_labels = []
        all_groups = []

        group_mapping = {}

        group_id = 0
        for video in self.videos:
            video_path = self.video_path(video)
            pose_est = self.load_pose_est(video_path)
            # fps used to scale some features from per pixel time unit to
            # per second
            fps = get_fps(str(video_path))

            for identity in pose_est.identities:
                group_mapping[group_id] = {'video': video, 'identity': identity}

                features = fe.IdentityFeatures(video, identity,
                                               self.feature_dir, pose_est,
                                               fps=fps)

                labels = self.load_video_labels(video).get_track_labels(
                    str(identity), behavior).get_labels()

                per_frame_features = features.get_per_frame(labels)
                window_features = features.get_window_features(window_size,
                                                               labels)

                all_per_frame.append(per_frame_features)
                all_window.append(window_features)
                all_labels.append(labels[labels != TrackLabels.Label.NONE])

                # should be a better way to do this, but I'm getting the number
                # of frames in this group by looking at the shape of one of
                # the arrays included in the per frame features
                all_groups.append(
                    np.full(per_frame_features['angles'].shape[0],
                            group_id))
                group_id += 1

                if progress_callable is not None:
                    progress_callable()

        return {
            'window': fe.IdentityFeatures.merge_window_features(all_window),
            'per_frame': fe.IdentityFeatures.merge_per_frame_features(
                all_per_frame),
            'labels': np.concatenate(all_labels),
            'groups': np.concatenate(all_groups),
        }, group_mapping

    @staticmethod
    def __hash_file(file: Path):
        """ return hash """
        chunk_size = 8192
        with file.open('rb') as f:
            h = hashlib.blake2b(digest_size=20)
            c = f.read(chunk_size)
            while c:
                h.update(c)
                c = f.read(chunk_size)
        return h.hexdigest()

    def __update_version(self):
        """ update the version number saved in project metadata """
        # only update if the version in the metadata is different from current
        version = self._metadata.get('version')
        if version != version_str():
            self.save_metadata({'version': version_str()})

    def __has_pose(self, vid: str):
        """ check to see if a video has a corresponding pose file """
        path = self._project_dir_path / vid

        try:
            get_pose_path(path)
        except ValueError:
            return False
        return True

    def __read_counts(self, video, behavior):
        """
        read labeled frame and bout counts from json file
        :return: list of labeled frame and bout counts for each identity for the
        specified behavior. Each element in the list is a tuple of the form
        (
            identity,
            (behavior frame count, not behavior frame count)
            (behavior bout count, not behavior bout count)
        )
        """
        video_filename = Path(video).name
        path = self._annotations_dir / Path(video_filename).with_suffix('.json')

        counts = []

        if path.exists():
            with path.open() as f:
                labels = json.load(f).get('labels')
                for identity in labels:
                    blocks = labels[identity].get(behavior, [])
                    frames_behavior = 0
                    frames_not_behavior = 0
                    bouts_behavior = 0
                    bouts_not_behavior = 0
                    for b in blocks:
                        if b['present']:
                            bouts_behavior += 1
                            frames_behavior += b['end'] - b['start'] + 1
                        else:
                            bouts_not_behavior += 1
                            frames_not_behavior += b['end'] - b['start'] + 1

                    counts.append((identity,
                                   (frames_behavior, frames_not_behavior),
                                   (bouts_behavior, bouts_not_behavior)))
        return counts

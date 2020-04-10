from .track_labels import TrackLabels


class VideoLabels:
    """
    store the labels associated with a video file
    """
    def __init__(self, filename, num_frames):
        self._filename = filename
        self._num_frames = num_frames
        self._identity_labels = {}

    def get_track_labels(self, identity, behavior):
        """ return a TrackLabels for an identity & behavior """
        identity_labels = self._identity_labels.get(identity)

        if identity_labels is None:
            self._identity_labels[identity] = {}

        track_labels = self._identity_labels[identity].get(behavior)

        if track_labels is None:
            self._identity_labels[identity][behavior] = \
                TrackLabels(self._num_frames)

        return self._identity_labels[identity][behavior]

    def export(self):
        """
        export all labels for this video in a json serializable nested  dict
        """
        labels = {}
        for identity in self._identity_labels:
            labels[identity] = {}
            for behavior in self._identity_labels[identity]:
                labels[identity][behavior] = \
                    self._identity_labels[identity][behavior].export()

        return {
            'file': self._filename,
            'num_frames': self._num_frames,
            'labels': labels
        }

    @classmethod
    def load(cls, video_label_dict):
        """
        return a VideoLabels object initialized with data from a dict previously
        exported using the export() method
        """
        labels = cls(video_label_dict['file'], video_label_dict['num_frames'])
        for identity in video_label_dict['labels']:
            labels._identity_labels[identity] = {}
            for behavior in video_label_dict['labels'][identity]:
                labels._identity_labels[identity][behavior] = TrackLabels.load(
                    video_label_dict['num_frames'],
                    video_label_dict['labels'][identity][behavior])

        return labels

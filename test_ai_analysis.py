iled import os
import unittest
from app import analyze_video_for_moments, generate_metadata_from_moments, generate_short_clips

class TestAIAnalysis(unittest.TestCase):
    def test_analyze_video_for_moments(self):
        # Test with a sample video (you need to provide a test video)
        test_video = 'test_video.mp4'
        if not os.path.exists(test_video):
            self.skipTest("Test video not found")

        moments, frame_times, frames = analyze_video_for_moments(test_video)
        self.assertIsInstance(moments, list)
        self.assertGreater(len(moments), 0)
        for moment in moments:
            self.assertGreater(moment['end'] - moment['start'], 20)

    def test_generate_metadata(self):
        test_moments = [{
            'start': 10,
            'end': 30,
            'avg_intensity': 150,
            'avg_motion': 80
        }]
        metadata = generate_metadata_from_moments(test_moments, 'fortnite')
        self.assertIn('title', metadata)
        self.assertIn('description', metadata)
        self.assertIn('tags', metadata)
        self.assertIn('hashtags', metadata)

    def test_generate_short_clips(self):
        # Test with a sample video (you need to provide a test video)
        test_video = 'test_video.mp4'
        if not os.path.exists(test_video):
            self.skipTest("Test video not found")

        test_moments = [{
            'start': 10,
            'end': 30
        }]
        output_dir = 'test_output'
        os.makedirs(output_dir, exist_ok=True)
        clips = generate_short_clips(test_video, test_moments, output_dir)
        self.assertIsInstance(clips, list)
        self.assertGreater(len(clips), 0)
        for clip in clips:
            self.assertTrue(os.path.exists(clip))

if __name__ == '__main__':
    unittest.main()
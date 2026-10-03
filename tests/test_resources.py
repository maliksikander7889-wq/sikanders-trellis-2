import unittest
from unittest.mock import Mock, patch
from resource_guard import validate_hardware, wait_worker


class ResourceTests(unittest.TestCase):
    def test_12gb_rejects_maximum_before_work(self):
        info={"total_gib":11.94}
        validate_hardware(1024,info=info)
        for resolution in (1536,2048):
            with self.assertRaisesRegex(ValueError,"memory limit"):
                validate_hardware(resolution,info=info)

    def test_pixal_does_not_silently_downgrade_2048(self):
        with self.assertRaisesRegex(ValueError,"Pixal3D supports"):
            validate_hardware(2048,"pixal3d",{"total_gib":48})

    def test_watchdog_stops_only_its_worker(self):
        process=Mock()
        process.poll.return_value=None
        with patch('resource_guard.memory_available',return_value=(6,1)), patch('resource_guard.stop_tree') as stop:
            with self.assertRaisesRegex(RuntimeError,"protect Windows"):
                wait_worker(process)
            stop.assert_called_once_with(process)

    def test_short_physical_memory_dip_does_not_stop_worker(self):
        process=Mock()
        process.poll.side_effect=[None,None,0]
        process.returncode=0
        with patch('resource_guard.memory_available',side_effect=[(1,8),(5,8)]), patch('resource_guard.stop_tree') as stop, patch('resource_guard.time.sleep'):
            self.assertEqual(wait_worker(process),0)
            stop.assert_not_called()

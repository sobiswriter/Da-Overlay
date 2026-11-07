import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ui.companion_dock import ACTION_WIDTH, ACTION_HEIGHT, ORB_SIZE, NativeCompanion, bubble_lifetime, split_bubbles, dock_position, radial_positions


class CompanionTests(unittest.TestCase):
    def test_context_menu_keeps_its_callbacks_alive_after_posting(self):
        hud = NativeCompanion.__new__(NativeCompanion)
        hud._root = Mock()
        hud._tk = Mock()
        hud._state = {"companions": []}
        hud._context_menu = None
        hud._radial = []
        hud._canvas = None
        menu, submenu = Mock(), Mock()
        hud._tk.Menu.side_effect = [menu, submenu]
        hud._menu(SimpleNamespace(x_root=100, y_root=100))
        menu.tk_popup.assert_called_once_with(100, 100)
        hud._root.focus_force.assert_called_once()
        menu.destroy.assert_not_called()

    def test_long_reply_is_not_lost_when_split_for_small_bubbles(self):
        text = "A useful thought. " * 80
        fragments = split_bubbles(text)
        self.assertTrue(all(len(p) <= 420 for p in fragments))
        self.assertEqual(" ".join(fragments).split(), text.split())

    def test_reading_time_has_a_floor_and_a_ceiling(self):
        self.assertGreaterEqual(bubble_lifetime("Hi"), 10)
        self.assertGreater(bubble_lifetime("a " * 150), bubble_lifetime("Hi"))
        self.assertLessEqual(bubble_lifetime("word " * 5000), 45)

    def test_plain_bubbles_preserve_code_names_and_multiplication(self):
        self.assertEqual(split_bubbles("## A thought\nUse **C#** and `x*y` instead of *guessing*."), ["A thought Use C# and x*y instead of guessing."])

    def test_orb_snaps_to_nearest_edge_and_stays_in_work_area(self):
        bounds = (-1280, 0, 0, 1024)
        self.assertEqual(dock_position(-1200, -50, bounds), (-1268, 12))
        self.assertEqual(dock_position(-20, 2000, bounds), (-60, 964))

    def test_orb_can_stay_in_the_middle_of_a_monitor(self):
        self.assertEqual(dock_position(700, 400, (0, 0, 1920, 1080)), (700, 400))

    def test_radial_actions_fit_at_every_corner_including_negative_monitors(self):
        bounds = (-1280, -100, 0, 924)
        for x, y in [(-1268, -88), (-76, -88), (-1268, 848), (-76, 848), (-640, 400)]:
            positions = radial_positions(x, y, bounds)
            for px, py in positions:
                self.assertTrue(-1272 <= px <= -80)
                self.assertTrue(-92 <= py <= 846)
            for i, (px, py) in enumerate(positions):
                for qx, qy in positions[i+1:]:
                    self.assertTrue(abs(px-qx) >= 50 or abs(py-qy) >= 50, "Radial actions overlap")

    def test_four_actions_with_readable_labels_fit_without_overlapping(self):
        bounds = (-1280, -100, 0, 924)
        for x, y in [(-1268, -88), (-76, -88), (-1268, 848), (-76, 848), (-640, 400)]:
            positions = radial_positions(x, y, bounds, count=4)
            self.assertEqual(len(positions), 4)
            for i, (px, py) in enumerate(positions):
                self.assertTrue(bounds[0]+8 <= px <= bounds[2]-ACTION_WIDTH-8)
                self.assertTrue(bounds[1]+8 <= py <= bounds[3]-ACTION_HEIGHT-8)
                for qx, qy in positions[i+1:]:
                    self.assertTrue(abs(px-qx) >= ACTION_WIDTH+8 or abs(py-qy) >= ACTION_HEIGHT+8)

    def test_four_radial_actions_fit_on_a_small_monitor(self):
        for x, y in [(12, 12), (344, 12), (12, 444), (344, 444)]:
            positions = radial_positions(x, y, (0, 0, 420, 520), count=4)
            self.assertEqual(len(positions), 4)
            self.assertTrue(all(8 <= px <= 420-ACTION_WIDTH-8 and 8 <= py <= 520-ACTION_HEIGHT-8 for px, py in positions))

    def test_radial_controls_are_small_and_the_default_fan_is_compact(self):
        self.assertEqual(ORB_SIZE, 48)
        self.assertEqual((ACTION_WIDTH, ACTION_HEIGHT), (64, 60))
        positions = radial_positions(1860, 880, (0, 0, 1920, 1080), count=4)
        self.assertLessEqual(max(y for x, y in positions)-min(y for x, y in positions)+ACTION_HEIGHT, 280)

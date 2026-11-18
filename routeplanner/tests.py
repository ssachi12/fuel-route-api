from django.test import SimpleTestCase
from .services.planner import Node, plan_fuel_stops


class PlannerTests(SimpleTestCase):
    def test_short_trip_needs_no_stops(self):
        self.assertEqual(plan_fuel_stops(300, [Node(100, 3.5, {})]), [])

    def test_buys_where_cheaper_and_gallons_add_up(self):
        nodes = [Node(400, 4.0, {}), Node(800, 3.0, {})]
        p = plan_fuel_stops(1200, nodes)
        self.assertEqual([x.node.mile for x in p], [400, 800])
        self.assertAlmostEqual(sum(x.gallons for x in p), (1200 - 500) / 10)

    def test_gap_too_large_raises(self):
        from .services.planner import NoFeasiblePlan
        with self.assertRaises(NoFeasiblePlan):
            plan_fuel_stops(1500, [Node(100, 3.0, {})])
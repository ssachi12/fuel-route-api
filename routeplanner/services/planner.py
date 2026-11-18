from dataclasses import dataclass


MIN_SAVINGS = 0.05   # $/gal


class NoFeasiblePlan(Exception): ...


@dataclass
class Node:
    mile: float      # distance along the route
    price: float     # $/gal
    station: dict | None


@dataclass
class Purchase:
    node: Node
    gallons: float

    @property
    def cost(self):
        return self.gallons * self.node.price


def plan_fuel_stops(total_miles, stations, range_miles=500.0, mpg=10.0):
    """
    Cheapest-fuel greedy. Start with a full tank.
    At each stop: if a cheaper stop is reachable on a full tank, buy only enough to get there;
    otherwise fill up and head to the cheapest stop in range.
    """
    cap = range_miles / mpg
    nodes = sorted(stations, key=lambda n: n.mile) + [Node(total_miles, 0.0, None)]
    cur_mile, cur_price, cur_node, fuel = 0.0, float("inf"), None, cap
    purchases = []

    while cur_mile < total_miles - 1e-9:
        window = [n for n in nodes if cur_mile < n.mile <= cur_mile + range_miles]
        if not window:
            raise NoFeasiblePlan(f"No fuel station within {range_miles:.0f} miles after mile {cur_mile:.0f}")
        target = next((n for n in window if n.price < cur_price - MIN_SAVINGS), None)
        if target:
            buy = max(0.0, (target.mile - cur_mile) / mpg - fuel)
        else:
            cheapest = min(n.price for n in window)
            # among stations within MIN_SAVINGS of the cheapest, go to the farthest one
            target = max((n for n in window if n.price <= cheapest + MIN_SAVINGS),
                         key=lambda n: n.mile)
            buy = cap - fuel
        if buy > 1e-9:
            purchases.append(Purchase(cur_node, buy))
        fuel += buy - (target.mile - cur_mile) / mpg
        cur_mile, cur_price, cur_node = target.mile, target.price, target
    return purchases
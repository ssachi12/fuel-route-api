from urllib.parse import urlencode
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET
from .services.external import LocationError, RoutingError
from .services.planner import NoFeasiblePlan
from .services.trip import build_plan

import requests


def _params(request):
    start, finish = request.GET.get("start", "").strip(), request.GET.get("finish", "").strip()
    if not start or not finish:
        raise ValueError("Both 'start' and 'finish' query parameters are required")
    return start, finish


@require_GET
def route_api(request):
    try:
        start, finish = _params(request)
        result = build_plan(start, finish)
    except (ValueError, LocationError) as e:
        return JsonResponse({"error": str(e)}, status=400)
    except NoFeasiblePlan as e:
        return JsonResponse({"error": str(e)}, status=422)
    except (RoutingError, requests.RequestException) as e:
        return JsonResponse({"error": f"Routing service problem: {e}"}, status=502)
    qs = urlencode({"start": start, "finish": finish})
    return JsonResponse({**result, "map_url": request.build_absolute_uri(reverse("route-map") + "?" + qs)})


@require_GET
def route_map(request):
    start, finish = _params(request)
    api_url = reverse("route-api") + "?" + urlencode({"start": start, "finish": finish})
    return render(request, "routeplanner/map.html", {"api_url": api_url})
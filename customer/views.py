from django.http import JsonResponse
from django.shortcuts import render

from employee.models import Employee

def employee_names_api(request):
    employee_names = (
        Employee.objects.filter(deleted_at__isnull=True)
        .order_by("name")
        .values_list("name", flat=True)
        .distinct()
    )
    return JsonResponse({"names": list(employee_names)})

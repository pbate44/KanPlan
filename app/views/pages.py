from django.shortcuts import redirect, render


def home(request):
    return redirect('dashboard' if request.user.is_authenticated else 'login')

def docs(request):
    return render(request, 'docs.html')


from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .helpers import MAX_BOARDS_PER_USER
from app.models import Board


@login_required
def dashboard(request):
    boards = list(Board.objects.filter(owner=request.user).order_by('-updated_at'))

    return render(request, 'dashboard.html', {
        'boards':      boards,
        'max_boards':  MAX_BOARDS_PER_USER,
        'board_count': len(boards),
    })

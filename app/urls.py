from django.urls import path

from app.views.ai import card_ai_chat, card_ai_history, list_chat_sessions, new_chat_session, delete_chat_session
from app.views.attachments import delete_attachment, get_attachments, upload_attachment, view_attachment
from app.views.board_ai import (
    board_ai_chat,
    board_ai_delete_session,
    board_ai_history,
    board_ai_new_session,
    board_ai_resolve_action,
    board_ai_sessions,
)
from app.views.auth import delete_account, goodbye, login_view, logout_view, signup_view
from app.views.board import (
    board_detail,
    create_board,
    delete_board,
    get_board_details,
    remove_board_image,
    update_board,
    update_board_title,
    upload_board_image,
)
from app.views.card import (
    add_card,
    card_detail,
    delete_card,
    delete_log_entry,
    export_card_log_pdf,
    update_card_color,
    update_card_description,
    update_card_priority,
    update_log_entry,
)
from app.views.column import (
    add_column,
    delete_column,
    save_column_sort_order,
    update_card_position_manual,
    update_column_name,
)
from app.views.dashboard import dashboard
from app.views.pages import docs, home
from app.views.settings import (
    edit_password,
    edit_theme,
    edit_username,
    get_ai_models,
    save_ai_connection,
    save_ai_model,
    test_ai_connection,
    user_settings,
)
from app.views.subtasks import add_subtask, delete_subtask, list_subtasks, toggle_subtask, update_subtask
from app.views.swimlane import add_swimlane, delete_swimlane, update_swimlane_name

urlpatterns = [

    path('',                    home,               name='home'),
    path('login/',              login_view,         name='login'),
    path('sign-up/',            signup_view,        name='signup'),
    path('logout/',             logout_view,        name='logout'),
    path('docs/',               docs,               name='docs'),

    path("settings/delete-account/", delete_account, name="delete_account"),
    path("goodbye/",                 goodbye,        name="goodbye"),

    path('board/<int:board_id>/',            board_detail,      name='board_detail'),
    path('cards/<int:card_id>/',             card_detail,       name='card_detail'),
    path('cards/<int:card_id>/export_pdf/',  export_card_log_pdf, name='export_card_log_pdf'),
    path('add-card/',                        add_card,          name='add_card'),
    path('update-board-title/<int:board_id>/', update_board_title, name='update_board_title'),
    path('add-column/',                      add_column,        name='add_column'),
    path('update-column-name/<int:column_id>/', update_column_name, name='update_column_name'),
    path('delete-column/<int:column_id>/',   delete_column,     name='delete_column'),
    path('add-swimlane/',                    add_swimlane,      name='add_swimlane'),
    path('update-swimlane-name/<int:swimlane_id>/', update_swimlane_name, name='update_swimlane_name'),
    path('delete-swimlane/<int:swimlane_id>/', delete_swimlane, name='delete_swimlane'),
    path('save-column-sort-order/',          save_column_sort_order, name='save_column_sort_order'),
    path('update-card-position-manual/',     update_card_position_manual, name='update_card_position_manual'),

    path('delete-card/<int:card_id>/',                   delete_card,             name='delete_card'),
    path('update-card-description/<int:card_id>/',       update_card_description, name='update_card_description'),
    path('update-card-priority/<int:card_id>/',          update_card_priority,    name='update_card_priority'),
    path('update-card-color/<int:card_id>/',             update_card_color,       name='update_card_color'),
    path('delete-log-entry/<int:entry_id>/',             delete_log_entry,        name='delete_log_entry'),
    path('update-log-entry/<int:entry_id>/',             update_log_entry,        name='update_log_entry'),
    path('cards/<int:card_id>/attachments/upload/',      upload_attachment,       name='upload_attachment'),
    path('cards/<int:card_id>/attachments/',             get_attachments,         name='get_attachments'),
    path('attachments/<int:attachment_id>/view/',        view_attachment,         name='view_attachment'),
    path('attachments/<int:attachment_id>/delete/',      delete_attachment,       name='delete_attachment'),

    path('card/<int:card_id>/ai-chat/',                                      card_ai_chat,        name='card_ai_chat'),
    path('card/<int:card_id>/ai-chat/history/',                              card_ai_history,     name='card_ai_chat_history'),
    path('card/<int:card_id>/ai-chat/sessions/',                             list_chat_sessions,  name='list_chat_sessions'),
    path('card/<int:card_id>/ai-chat/sessions/new/',                         new_chat_session,    name='new_chat_session'),
    path('card/<int:card_id>/ai-chat/sessions/<int:session_id>/delete/',     delete_chat_session, name='delete_chat_session'),

    path('board/<int:board_id>/ai-chat/',                                    board_ai_chat,           name='board_ai_chat'),
    path('board/<int:board_id>/ai-chat/history/',                            board_ai_history,        name='board_ai_history'),
    path('board/<int:board_id>/ai-chat/sessions/',                           board_ai_sessions,       name='board_ai_sessions'),
    path('board/<int:board_id>/ai-chat/sessions/new/',                       board_ai_new_session,    name='board_ai_new_session'),
    path('board/<int:board_id>/ai-chat/sessions/<int:session_id>/delete/',   board_ai_delete_session, name='board_ai_delete_session'),
    path('board/<int:board_id>/ai-chat/actions/<int:message_id>/confirm/',   board_ai_resolve_action, {'decision': 'confirm'}, name='board_ai_confirm_action'),
    path('board/<int:board_id>/ai-chat/actions/<int:message_id>/cancel/',    board_ai_resolve_action, {'decision': 'cancel'},  name='board_ai_cancel_action'),

    path('cards/<int:card_id>/subtasks/',       list_subtasks,   name='list_subtasks'),
    path('cards/<int:card_id>/subtasks/add/',   add_subtask,     name='add_subtask'),
    path('subtasks/<int:subtask_id>/toggle/',   toggle_subtask,  name='toggle_subtask'),
    path('subtasks/<int:subtask_id>/update/',   update_subtask,  name='update_subtask'),
    path('subtasks/<int:subtask_id>/delete/',   delete_subtask,  name='delete_subtask'),

    path('dashboard/',                          dashboard,         name='dashboard'),
    path('boards/create/',                      create_board,      name='create_board'),
    path('boards/<int:board_id>/update/',       update_board,      name='update_board'),
    path('boards/<int:board_id>/delete/',       delete_board,      name='delete_board'),
    path('boards/<int:board_id>/upload-image/', upload_board_image, name='upload_board_image'),
    path('boards/<int:board_id>/remove-image/', remove_board_image, name='remove_board_image'),
    path('boards/<int:board_id>/details/',      get_board_details,  name='get_board_details'),

    path('user_settings/',                  user_settings,      name='user_settings'),
    path('user_settings/edit_username/',    edit_username,      name='edit_username'),
    path('user_settings/edit_password/',    edit_password,      name='edit_password'),
    path('user_settings/edit_theme/',       edit_theme,         name='edit_theme'),
    path('settings/ai/model/save/',          save_ai_model,          name='save_ai_model'),
    path('settings/ai/models/',             get_ai_models,          name='get_ai_models'),
    path('settings/ai/connection/save/',    save_ai_connection,     name='save_ai_connection'),
    path('settings/ai/connection/test/',    test_ai_connection,     name='test_ai_connection'),

]

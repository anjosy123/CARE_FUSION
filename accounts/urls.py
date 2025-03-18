from django.urls import path, include
from . import views
from .views import (
    index, about, organizations_home, contact, services, handlelogin, 
    handlesignup, handlelogout, register_organization, org_logout, handle_service_request,
    verify_email
)
from django.contrib.auth import views as auth_views
from . import consumers

urlpatterns = [
    # Social Auth
    path('social-auth/', include('social_django.urls', namespace='social')),
    path('', index, name='index'),  # Homepage pointing to index view
    # path('accounts', include('allauth.urls')),  # For Google and other social logins
    path('contact', contact, name='contact'),
    path('about', about, name='about'),
    path('services', services, name='services'),
    path('handle-service-request/', handle_service_request, name='handle_service_request'),
    path('submit-service-request/<str:org_id>/', views.submit_service_request, name='submit_service_request'),
    # User login, signup, and logout
    path('login', handlelogin, name='login'),
    path('signup', handlesignup, name='signup'),
    path('logout', handlelogout, name='logout'),
    path('user_notification_dashboard', views.user_notification_dashboard, name='user_notification_dashboard'),
    # Organization login, signup, and logout
    path('organizations_home', organizations_home, name='organizations_home'),
    path('org_login', handlelogin, name='handle_org_login'),
    path('org_signup', register_organization, name='org_signup'),
    path('org_logout', org_logout, name='org_logout'),
    
    # Provider routes
    path('providers', views.providers_list, name='providers'),
    
    # Password reset and management
    path('forgot-password', views.forgot_password, name='forgot_password'),
    path('verify-code/<str:email>/', views.verify_code, name='verify_code'),
    path('reset-password/<str:email>/', views.reset_password, name='reset_password'),
    
    # Admin dashboard and user management
    path('admin_dashboard', views.admin_dashboard, name='admin_dashboard'),
    path('manage-users', views.manage_users, name='manage_users'),
    path('edit-user/<int:user_id>', views.edit_user, name='edit_user'),
    path('delete-user/<int:user_id>', views.delete_user, name='delete_user'),
    
    path('approve-request/<int:request_id>/', views.approve_request, name='approve_request'),
    
    # Approve organizations
    path('approve-organizations', views.approve_organizations, name='approve_organizations'),
    path('approve-organization/<int:org_id>', views.approve_organization, name='approve_organization'),
    
    # User and organization dashboards
    path('patients_dashboard/', views.patients_dashboard, name='patients_dashboard'),
    path('palliatives_dashboard', views.palliatives_dashboard, name='palliatives_dashboard'),

    # Organizations Details
    path('organizations/<int:id>/', views.organization_detail, name='organization_detail'),
    
    # Get service requests
    path('api/service-requests/<int:request_id>/', views.get_service_request_detail, name='service_request_detail'),
    path('service-request/<int:request_id>/', views.service_request_detail, name='service_request_detail'),
    path('patient_details/<int:request_id>/', views.patient_details, name='patient_details'),
    path('service-requests/', views.service_requests, name='service_requests'),
    path('edit-service-request/<int:request_id>/', views.edit_service_request, name='edit_service_request'),
    path('delete-service-request/<int:request_id>/', views.delete_service_request, name='delete_service_request'),
    path('approved-rejected-requests/', views.approved_rejected_requests, name='approved_rejected_requests'),
    path('pending-requests/', views.pending_requests, name='pending_requests'),
    path('request/<int:request_id>/view/', views.view_request, name='view_request'),
    path('request/<int:request_id>/approve/', views.approve_request, name='approve_request'),
    path('request/<int:request_id>/reject/', views.reject_request, name='reject_request'),

    # Organizations Services
    path('services/', views.service_list, name='service_list'),
    path('services/create/', views.service_create, name='service_create'),
    path('services/<int:pk>/edit/', views.service_edit, name='service_edit'),
    path('services/<int:pk>/delete/', views.service_delete, name='service_delete'),
    path('approve-request/<int:request_id>/', views.approve_request, name='approve_request'),
    
    # Staff details
    path('staff/', views.staff_list, name='staff_list'),
    # path('staff/add/', views.add_staff, name='add_staff'),
    path('staff/<int:staff_id>/toggle-status/', views.toggle_staff_status, name='toggle_staff_status'),
    path('patient-assignments/', views.patient_assignment_list, name='patient_assignment_list'),
    path('assign-patient/', views.assign_patient, name='assign_patient'),
    path('unassign-patient/<int:assignment_id>/', views.unassign_patient, name='unassign_patient'),
    # path('get-staff-details/', views.get_staff_details, name='get_staff_details'),
    # path('toggle-staff-status/', views.toggle_staff_status, name='toggle_staff_status'),
    # path('edit-staff/<int:staff_id>/', views.edit_staff, name='edit_staff'),
    path('staff-list/', views.staff_list, name='staff_list'),
    
    # path('add-staff/', views.add_staff, name='add_staff'),
    # path('edit-staff/<int:staff_id>/', views.edit_staff, name='edit_staff'),
    # path('toggle-staff-status/', views.toggle_staff_status, name='toggle_staff_status'),
    # path('get-staff-details/', views.get_staff_details, name='get_staff_details'),
    
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.add_staff, name='add_staff'),
    path('staff/<int:staff_id>/edit/', views.edit_staff, name='edit_staff'),
    path('staff/<int:staff_id>/toggle/', views.toggle_staff_status, name='toggle_staff_status'),
    # path('confirm-staff-email/<str:token>/', views.confirm_staff_email, name='confirm_staff_email'),
    
    # Email verification
    path('verify-email/<str:token>/<str:is_organization>/', views.verify_email, name='verify_email'),
    path('verify-user-email/<str:token>/', views.verify_user_email, name='verify_user_email'),
    
    # Force password change for staff members
    # path('change_staff_password/', views.change_staff_password, name='change_staff_password'),
    path('doctor/dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('nurse/dashboard/', views.nurse_dashboard, name='nurse_dashboard'),
    path('volunteer/dashboard/', views.volunteer_dashboard, name='volunteer_dashboard'),
    path('change_staff_password/', views.change_staff_password, name='change_staff_password'),
    path('confirm-staff-email/<str:uidb64>/<str:token>/', views.confirm_staff_email, name='confirm_staff_email'),
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/patient/<int:assignment_id>/', views.patient_detail, name='patient_detail'),
    path('staff/patient/<int:assignment_id>/add-note/', views.add_patient_note, name='add_patient_note'),
    path('staff/doctor/prescriptions/<int:assignment_id>/', views.manage_prescriptions, name='manage_prescriptions'),
    path('staff/doctor/prescriptions/edit/<int:prescription_id>/', views.edit_prescription, name='edit_prescription'),
    # path('staff/doctor/appointments/', views.manage_all_appointments, name='manage_all_appointments'),
    path('staff/doctor/appointments/<int:assignment_id>/', views.manage_appointments, name='manage_appointments'),
    path('staff/doctor/medical-history/<int:assignment_id>/', views.manage_medical_history, name='manage_medical_history'),
    path('notifications/', views.notification_center, name='notification_center'),
    path('messaging/', views.messaging, name='messaging'),
    path('appointments/available/', views.available_appointments, name='available_appointments'),
    path('appointments/book/<int:appointment_id>/', views.book_appointment, name='book_appointment'),
    path('appointments/emergency-request/', views.request_emergency_appointment, name='request_emergency_appointment'),
    path('schedule-appointment/', views.schedule_appointment, name='schedule_appointment'),
    path('batch-cancel-appointments/', views.batch_cancel_appointments, name='batch_cancel_appointments'),
    path('appointment/<int:appointment_id>/edit/', views.edit_appointment, name='edit_appointment'),
    path('appointment/<int:appointment_id>/cancel/', views.cancel_appointment, name='cancel_appointment'),
    path('staff/doctor/appointments/', views.manage_appointments, name='manage_all_appointments'),
    # path('reschedule-appointment/<int:appointment_id>/', views.reschedule_appointment, name='reschedule_appointment'),
    # path('cancel-appointment/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/doctor/reschedule-appointment/<int:appointment_id>/', views.reschedule_appointment, name='reschedule_appointment'),
    path('staff/cancel-appointment/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),
    # path('staff/schedule-appointment/<int:assignment_id>/', views.schedule_appointment, name='schedule_appointment'),
    
    # palliative organization team management
    
    path('teams/', views.team_list, name='team_list'),
    path('teams/create/', views.create_team, name='create_team'),
    path('teams/schedule-visit/', views.schedule_team_visit, name='schedule_team_visit'),
    path('teams/visits/', views.team_visit_list, name='team_visit_list'),
    path('teams/calendar/', views.team_visit_calendar, name='team_visit_calendar'),
    
    # Team management
    path('team-visit-calendar/', views.team_visit_calendar, name='team_visit_calendar'),
    path('reschedule-team-visit/<int:visit_id>/', views.reschedule_team_visit, name='reschedule_team_visit'),
    path('get-available-slots/<int:team_id>/<str:date>/', views.get_available_slots, name='get_available_slots'),
    path('visit-checklist-notes/<int:visit_id>/', views.visit_checklist_notes, name='visit_checklist_notes'),
    path('team/dashboard/', views.team_dashboard, name='team_dashboard'),
    path('team-dashboard/change-password/', views.team_dashboard_change_password, name='team_dashboard_change_password'),
    path('team/<int:team_id>/', views.team_detail, name='team_detail'),
    path('request-appointment/', views.request_appointment, name='request_appointment'),
    path('assigned-teams/', views.assigned_teams, name='assigned_teams'),
    path('notification-center/', views.notification_center, name='notification_center'),
    path('patient-profile/', views.patient_profile, name='patient_profile'),
    path('org-profile/', views.org_profile, name='org_profile'),
    path('request-team-visit/', views.request_team_visit, name='request_team_visit'),
    path('team/<int:team_id>/request-visit/', views.request_team_visit_specific, name='request_team_visit_specific'),
    path('my-visit-requests/', views.patient_visit_requests, name='patient_visit_requests'),
    path('patient-notifications/', views.patient_notifications, name='patient_notifications'),
    path('admin/edit-organization/<int:org_id>/', views.edit_organization, name='edit_organization'),
    path('dashboard/toggle-organization-status/<int:org_id>/', views.toggle_organization_status, name='toggle_organization_status'),
    path('patient/service-requests/', views.patient_service_requests, name='patient_service_requests'),
    path('patient-profile/', views.patient_profile, name='patient_profile'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('patient/settings/', views.patient_settings, name='patient_settings'),
    path('patient/change-password/', views.change_password, name='change_password'),
    path('patient/update-notification-preferences/', views.update_notification_preferences, name='update_notification_preferences'),
    path('patient/update-privacy-settings/', views.update_privacy_settings, name='update_privacy_settings'),
    path('patient/deactivate-account/', views.deactivate_account, name='deactivate_account'),
    path('teams/<int:team_id>/edit/', views.edit_team, name='edit_team'),
    path('teams/<int:team_id>/toggle-status/', views.toggle_team_status, name='toggle_team_status'),
    path('team-visit/<int:visit_id>/edit/', views.edit_team_visit, name='edit_team_visit'),
    path('team-visit/<int:visit_id>/cancel/', views.cancel_team_visit, name='cancel_team_visit'),
    path('toggle-staff-status/<int:staff_id>/', views.toggle_staff_status, name='toggle_staff_status'),

    path('request-service/<int:org_id>/', views.service_request_form, name='service_request_form'),
    path('upcoming-team-visits/', views.upcoming_team_visits, name='upcoming_team_visits'),
    path('save-patient-data/', views.save_patient_data, name='save_patient_data'),
    path('visit-report/<int:visit_id>/', views.visit_report, name='visit_report'),
       
    path('get-patient-details/<int:patient_id>/', views.get_patient_details, name='get_patient_details'),
    
    path('organizations-list/', views.organizations_list, name='organizations_list'),
    path('get-team-details/<int:team_id>/', views.get_team_details, name='get_team_details'),
    path('api/predict-priority/', views.predict_priority, name='predict_priority'),
    path('api/model-metrics/', views.model_metrics, name='model_metrics'),
    
    path('api/predict-priority/', views.predict_priority, name='predict_priority'),
    path('api/model-metrics/', views.model_metrics, name='model_metrics'),
    path('priority-dashboard/', views.priority_dashboard, name='priority_dashboard'),
    path('patient-detail/<int:patient_id>/', views.patient_detail, name='patient_detail'),
    path('export-priority-report/', views.export_priority_report, name='export_priority_report'),
    path('retrain-model/', views.retrain_model, name='retrain_model'),
    path('equipment/<int:org_id>/', views.equipment_list, name='equipment_list'),
    path('initiate-rental/<int:equipment_id>/', views.initiate_rental, name='initiate_rental'),
    path('confirm-rental-payment/', views.confirm_rental_payment, name='confirm_rental_payment'),
    path('manage-equipment/', views.manage_equipment, name='manage_equipment'),
    path('api/equipment/save/', views.save_equipment, name='save_equipment'),
    path('api/equipment/<int:equipment_id>/', views.get_equipment_details, name='get_equipment_details'),
    path('api/equipment/<int:equipment_id>/delete/', views.delete_equipment, name='delete_equipment'),
    path('api/equipment/<int:equipment_id>/toggle-status/', views.toggle_equipment_status, name='toggle_equipment_status'),
    path('rental-requests/', views.rental_requests, name='rental_requests'),
    path('api/rental/<int:rental_id>/details/', views.get_rental_details, name='get_rental_details'),
    path('api/rental/assign-delivery/', views.assign_delivery, name='assign_delivery'),
    path('api/rental/<int:rental_id>/mark-returned/', views.mark_rental_returned, name='mark_rental_returned'),
    path('delivery-management/', views.delivery_management, name='delivery_management'),
    path('volunteer/dashboard/', views.volunteer_dashboard, name='volunteer_dashboard'),
    path('staff/logout/', views.staff_logout, name='staff_logout'),
    path('staff/my-deliveries/', views.staff_deliveries, name='staff_deliveries'),
    path('staff/delivery-history/', views.delivery_history, name='delivery_history'),
    path('api/delivery/<int:delivery_id>/accept/', views.accept_delivery, name='accept_delivery'),
    path('api/delivery/<int:delivery_id>/complete/', views.complete_delivery, name='complete_delivery'),
    path('patient/rentals/', views.patient_rentals, name='patient_rentals'),
    path('equipment/add/', views.add_equipment, name='add_equipment'),
    path('equipment/edit/<int:equipment_id>/', views.add_equipment, name='edit_equipment'),
    path('api/equipment/update/<int:equipment_id>/', views.update_equipment, name='update_equipment'),
    path('rental/<int:rental_id>/payment/', views.process_rental_payment, name='process_rental_payment'),
    path('rental/verify-payment/', views.verify_rental_payment, name='verify_rental_payment'),
    path('initiate-rental-request/<int:equipment_id>/', views.initiate_rental_request, name='initiate_rental_request'),
    path('api/rental/<int:rental_id>/approve/', views.approve_rental_request, name='approve_rental_request'),
    path('api/rental/<int:rental_id>/reject/', views.reject_rental_request, name='reject_rental_request'),
    path('api/rental/<int:rental_id>/history/', views.get_rental_history, name='get_rental_history'),
    path('rental/confirm/<int:rental_id>/', views.confirm_rental, name='confirm_rental'),
    path('rental-request/<int:equipment_id>/', views.rental_request, name='rental_request'),
    path('api/delivery/assign-volunteer/', views.assign_volunteer, name='assign_volunteer'),
    path('api/delivery/<int:delivery_id>/start/', views.start_delivery, name='start_delivery'),
    path('api/delivery/<int:delivery_id>/complete/', views.complete_delivery, name='complete_delivery'),
    path('api/delivery/<int:delivery_id>/update-location/', views.update_delivery_location, name='update_delivery_location'),
    path('api/delivery/<int:delivery_id>/mark-arrived/', views.mark_arrived, name='mark_arrived'),
    path('api/delivery/<int:delivery_id>/verify-otp/', views.verify_delivery_otp, name='verify_delivery_otp'),
    path('api/delivery/<int:delivery_id>/location/', views.get_delivery_location, name='get_delivery_location'),
    path('rental/calculate/<int:equipment_id>/', views.calculate_rental, name='calculate_rental'),
    path('api/create-deposit-order/<int:equipment_id>/', views.create_deposit_order, name='create_deposit_order'),
    path('api/verify-deposit-payment/', views.verify_deposit_payment, name='verify_deposit_payment'),
    path('api/check-rental-status/', views.check_rental_status, name='check_rental_status'),
    path('api/cancel-rental-request/', views.cancel_rental_request, name='cancel_rental_request'),
    path('api/rental/<int:rental_id>/usage-details/', views.get_rental_usage_details, name='rental_usage_details'),
    path('api/rental/<int:rental_id>/end-service/', views.end_rental_service, name='end_rental_service'),
    path('api/rental/<int:rental_id>/org-details/', views.get_rental_org_details, name='rental_org_details'),
    path('team/visit/<int:visit_id>/record/', views.record_visit, name='record_visit'),
    path('track-location/<int:visit_id>/', views.track_patient_location, name='track_patient_location'),
    path('api/rental/<int:rental_id>/final-amount/', views.get_rental_final_amount, name='get_rental_final_amount'),
    path('rental/<int:rental_id>/payment/', views.rental_payment, name='rental_payment'),
    path('api/rental/request-extension/', views.request_rental_extension, name='request_rental_extension'),
    path('rental/<int:rental_id>/invoice/download/', views.download_rental_invoice, name='download_rental_invoice'),
]


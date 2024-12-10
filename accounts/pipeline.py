def set_role(backend, user, response, *args, **kwargs):
    session = kwargs['request'].session
    session['user_id'] = user.id
    session['username'] = user.username
    session['email'] = user.email
    session['role'] = 'user'
    return

def mark_email_verified(backend, user, response, *args, **kwargs):
    if backend.name == 'google-oauth2':
        user.is_email_verified = True
        user.save()
    return None
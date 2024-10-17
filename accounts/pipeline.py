def set_role(backend, user, response, *args, **kwargs):
    session = kwargs['request'].session
    session['user_id'] = user.id
    session['username'] = user.username
    session['email'] = user.email
    session['role'] = 'user'
    return
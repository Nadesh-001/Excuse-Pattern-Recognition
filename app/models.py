from flask_login import UserMixin

class User(UserMixin):
    """
    Neural_Protocol User model for Flask-Login compatibility.
    """
    def __init__(self, user_data):
        self.id = user_data['id']
        self.name = user_data['full_name']
        self.email = user_data['email']
        self.role = user_data['role']
        self.active_status = user_data.get('active_status', True)
